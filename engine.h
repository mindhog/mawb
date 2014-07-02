#ifndef awb_engine_h_
#define awb_engine_h_

#include <spug/RCBase.h>
#include <spug/RCPtr.h>
#include <spug/Time.h>

#include "awb_types.h"

namespace spug {
    class Reactor;
}

namespace awb {

class Event;
class TimeMaster;
SPUG_RCPTR(Track);

// Abstract class that is associated with an event source.  Implementations
// should control processing of the event.
class EventDispatcher : public spug::RCBase {
    public:
        virtual void onEvent(Event *event) = 0;
};

SPUG_RCPTR(EventDispatcher);

class DebugDispatcher : public EventDispatcher {
    public:
        virtual void onEvent(Event *event);
};


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

    public:
        InputDispatcher(TimeMaster *timeMaster, Track *recordTrack = 0,
                        EventDispatcher *consumer = 0
                        );

        virtual void onEvent(Event *event);

        void setConsumer(EventDispatcher *consumer);

        void setRecordTrack(Track *track);
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
        uint32 getTicks() const;

        // Reset the current time.
        void reset();

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
class Controller {

    private:
        spug::Reactor &reactor;
        enum State {
            idle,
            play,
            record
        };

    public:

        Controller(spug::Reactor &reactor);
        void runOnce();
};

} // namespace awb

#endif
