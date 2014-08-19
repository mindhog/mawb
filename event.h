
#ifndef awb_event_h_
#define awb_event_h_

#include <vector>
#include <spug/RCBase.h>
#include <spug/RCPtr.h>

#include "awb_types.h"

namespace awb {

SPUG_RCPTR(Event);

class Event : public spug::RCBase {

    public:
        uint32 time;

        Event(uint32 time) : time(time) {}

        class StatAndString {
            byte status;
            std::string rep;

            StatAndString(uint8_t status, char *rep, unsigned int size) :
                status(status),
                rep(rep, size)  {
            }

            StatAndString(uint8_t status, const std::string &rep) :
                status(status), rep(rep) {
            }
        };

        enum Type {
            NOTE_ON,
            NOTE_OFF,
            PROGRAM_CHANGE
        };

        virtual Type getType() const = 0;

        // Returns true if the event is a ChannelEvent.
        bool isChannelEvent() const {
            Type type = getType();
            return type == NOTE_ON || type == NOTE_OFF ||
                   type == PROGRAM_CHANGE;
        }

        // Writes the event to 'out', a midi stream.  /status/ is the
        // current, running status byte, both an input and output parameter.
        virtual void writeMidi(byte &status, std::ostream &out) const = 0;

        // Write the event to 'out' along with its timestamp.
        void writeMidiWithTime(byte &status, uint lastTime,
                               std::ostream &out
                               ) const;

        virtual void formatTo(std::ostream &out) const = 0;

        // Make a copy of the event object.
        virtual EventPtr clone() const = 0;
};

// Abstract base class for all events that apply to a particular channel.
//
// Public variables:
//  channel: The channel that the event occurred on.  An integer from 0-15.
class ChannelEvent : public Event {
    public:
        byte channel;

        ChannelEvent(unsigned int time, byte channel) :
            Event(time),
            channel(channel) {
        }
};

SPUG_RCPTR(ChannelEvent);

//  Base class for midi "note on" and "note off" events, both of which have
//  the same public interface.
//
//  Public variables:
//  note: Numeric note (0-127)
//  velocity: Numeric velocity (0-127)
class NoteEvent : public ChannelEvent {

    public:
        byte note, velocity;

        NoteEvent(uint32 time, byte channel, byte note, byte velocity) :
            ChannelEvent(time, channel),
            note(note),
            velocity(velocity) {
        }
};

// Midi "note on" event.
class NoteOn : public NoteEvent {
    public:
        NoteOn(uint32 time, byte channel, byte note, byte velocity) :
            NoteEvent(time, channel, note, velocity) {
        }

    virtual Type getType() const {
        return NOTE_ON;
    }

    virtual void writeMidi(byte &status, std::ostream &out) const;
    virtual void formatTo(std::ostream &out) const;

    virtual EventPtr clone() const {
        return new NoteOn(time, channel, note, velocity);
    }
};

SPUG_RCPTR(NoteOn);

class NoteOff : public NoteEvent {
    public:
        NoteOff(uint32 time, byte channel, byte note, byte velocity = 0) :
            NoteEvent(time, channel, note, velocity) {
        }

    virtual Type getType() const {
        return NOTE_OFF;
    }

    virtual void writeMidi(byte &status, std::ostream &out) const;
    virtual void formatTo(std::ostream &out) const;

    virtual EventPtr clone() const {
        return new NoteOff(time, channel, note);
    }
};

SPUG_RCPTR(NoteOff);

SPUG_RCPTR(ProgramChange);

class ProgramChange : public ChannelEvent {
    public:
        byte program;

        ProgramChange(uint32 time, byte channel, byte program) :
            ChannelEvent(time, channel),
            program(program) {
        }

        virtual Type getType() const {
            return PROGRAM_CHANGE;
        }

        virtual void writeMidi(byte &status, std::ostream &out) const;
        virtual void formatTo(std::ostream &out) const;

        virtual EventPtr clone() const {
            return new ProgramChange(time, channel, program);
        }
};


SPUG_RCPTR(Track);

// A sequence of midi events.
class Track : public spug::RCBase {
    private:
        typedef std::vector<EventPtr> EventVec;
        EventVec events;

    public:

        // Add a new event.  The event must have a time later than the last
        // event already in the track.
        void add(Event *event);

        size_t size() const { return events.size(); }

        EventPtr get(size_t index) const { return events[index]; }

        EventVec::iterator begin() { return events.begin(); }
        EventVec::iterator end() { return events.end(); }

        /**
         * Read an entire track from the array of bytes.
         */
        static TrackPtr readFromMidi(const byte *data, size_t size);
};

/**
 * Reads midi events from a buffer.
 */
class MidiReader {
    private:
        byte status;
        const byte *cur, *end;

        inline byte readByte();
        uint readVarLen();

    public:
        /**
        * Construct a midi reader from the buffer.
        */
        MidiReader(const byte *data, size_t size) :
            cur(data),
            end(data + size) {
        }

//    // This gets called when we read an event with an unknown status byte.
//    // Override it to deal with special events.
//    Event readUserEvent();

        /** Read a single event. */
        EventPtr readEvent();

        /** Read an entire track. */
        TrackPtr readTrack(const char *name);
};

}  // namespace awb

inline std::ostream &operator <<(std::ostream &out, const awb::Event &event) {
    event.formatTo(out);
    return out;
}

#endif
