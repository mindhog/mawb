#ifndef awb_engine_h_
#define awb_engine_h_

#include <vector>
#include <map>

#include <spug/RCBase.h>
#include <spug/RCPtr.h>
#include <spug/Runnable.h>
#include <spug/Time.h>

#include "awb_types.h"
#include "mawb.pb.h"

namespace spug {
    class Reactor;
}

namespace mawb {
    class PBTrack;
}

namespace awb {

class Event;
class TimeMaster;
SPUG_RCPTR(Track);

// Abstract class that is associated with an event source.  Implementations
// should control processing of the event.
class EventDispatcher : public spug::RCBase {
    public:
        // A sequence of events that is written to the dispatcher on
        // initialization.
        std::string initialState;

        virtual void onEvent(Event *event) = 0;

        /**
         * Called when the engine is switched to "idle" state.
         */
        virtual void onIdle() = 0;

        /**
         * Send all of the events in the track to the dispatcher.
         */
        void sendEvents(const Track &track);
};

SPUG_RCPTR(EventDispatcher);

class DebugDispatcher : public EventDispatcher {
    public:
        virtual void onEvent(Event *event);
        virtual void onIdle();
};

SPUG_RCPTR(InputDispatcher);

// Processes input and optionally records it, dispatching events to an
// optional output dispatcher.
// The essential characteristic of the InputDispatcher is that it stores the
// current timestamp (as ticks since the beginning of the section) in the
// incoming event.  Both recording and dispatching to a consumer are optional,
// contingent on the record track and consumer not being null pointers.
class InputDispatcher : public EventDispatcher {
    private:
        TimeMaster *timeMaster;
        TrackPtr track;
        EventDispatcherPtr consumer;

        // If this is not -1, it is the output channel.  All ChannelEvents
        // have their channel value overriden to this before being passed on
        // to the consumer.
        int outputChannel;

    public:
        InputDispatcher(TimeMaster *timeMaster, Track *recordTrack = 0,
                        EventDispatcher *consumer = 0
                        );

        virtual void onEvent(Event *event);
        virtual void onIdle() {}

        void setConsumer(EventDispatcher *consumer);

        EventDispatcher *getConsumer() const { return consumer.get(); }

        void setRecordTrack(Track *track);

        void setOutputChannel(int outputChannel) {
            this->outputChannel = outputChannel;
        }

        /**
         * Returns the current record track and releases ownership of it.
         */
        TrackPtr releaseTrack();

        /**
         * Creates a track, initiating event recording.
         */
        void beginRecording();
};

// The TimeMaster keeps track of the current time as an offset of ticks since
// the beginning of the section.
class TimeMaster {
    private:

        // We track the last absolute time and the last "ticks since the
        // beginning" time so that given any absolute time value can be
        // converted.
        spug::Time lastAbsTime;
        uint32 lastTicks;

        // Current tempo in beats-per-minute
        uint32 bpm;

        // Current number of pulses (ticks) per beat.
        uint32 ppb;

    public:

        // Returns the current time as ticks since the beginning of the
        // session.
        uint32 getTicks();

        // Converts the specified number of ticks to a TimeDelta for the
        // current BPM and PPB.
        spug::TimeDelta ticksAsTimeDelta(uint32 ticks) const;

        // Set the current time to the specified value.
        void setTicks(uint32 time);

        // Set the current tempo.
        void setBPM(uint32 bpm) {
            this->bpm = bpm;
        }

        // Set the pulses per beat.  This should only be defined once at the
        // beginning of a project, because all timings are based on it.  All
        // events need to have their times adjusted if this is changed.
        void setPPB(uint32 ppb) {
            this->ppb = ppb;
        }
};

// The controller manages all events for MAWB.
class Controller : public spug::Runnable {

    private:
        spug::Reactor &reactor;
        TimeMaster &timeMaster;
        mawb::SequencerState state;

        struct TrackInfo {
            TrackPtr track;
            EventDispatcherPtr dispatcher;
            uint next;

            TrackInfo(Track *track, EventDispatcher *dispatcher) :
                track(track),
                dispatcher(dispatcher),
                next(0) {
            }
        };

        std::vector<TrackInfo> tracks;
        std::vector<InputDispatcherPtr> inputs;

        typedef std::map<std::string, EventDispatcherPtr> DispatcherMap;
        DispatcherMap dispatchers;

    public:

        Controller(spug::Reactor &reactor, TimeMaster &timeMaster);
        void runOnce();

        void setState(mawb::SequencerState state);

        /**
         * Transfers all of the input tracks from the input dispatchers to
         * the controller.
         */
        void storeInputTracks();

        /**
         * Creates tracks for all of the inputs, initiating event recording.
         */
        void beginRecording();

        /**
         * Add a serialized track to the current section.
         */
        void addTrack(const mawb::PBTrack &track);

        /**
         * Add the input dispatcher to the set managed by the controller.
         */
        void addInput(InputDispatcher *input) {
            inputs.push_back(input);
        }

        /**
         * This currently returns the first input dispatcher.  This is lame.
         * TODO: figure out the right way to manage input dispatchers.
         */
        InputDispatcherPtr getInputDispatcher() const {
            return inputs.front();
        }

        /**
         * Call setTicks() on current TimeMaster and locate the next event for
         * each track.
         */
        void setTicks(uint32 time);

        /**
         * Load the state from the specified state file.
         */
        void loadState(const std::string &filename);

        /**
         * Register an event dispatcher under the given name.
         */
        void setDispatcher(const std::string &name,
                           EventDispatcher *dispatcher
                           );

        /**
         * Returns the named event dispatcher or null if there is none by that
         * name.
         */
        EventDispatcherPtr getDispatcher(const std::string &name) const;

        /**
         * Save the state to the specified state file.
         */
        void saveState(const std::string &filename) const;

        virtual void run();


};

} // namespace awb

#endif
