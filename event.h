
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
            NOTE_OFF
        };

        virtual Type getType() const = 0;

        // Used to convert the event to a string of bytes suitable for inclusion
        // in a midi stream of some sort.  /status/ is the current, running
        // status byte.
        //
        // This method returns a tuple consisting of the new status byte and
        // the string representation of the event.
//        virtual StatAndString toMidiString(byte status) = 0;

//        virtual void writeTo(MidiWriter &writer) = 0;

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

    virtual void formatTo(std::ostream &out) const;

    virtual EventPtr clone() const {
        return new NoteOn(time, channel, note, velocity);
    }
};

class NoteOff : public NoteEvent {
    public:
        NoteOff(uint32 time, byte channel, byte note) :
            NoteEvent(time, channel, note, 0) {
        }

    virtual Type getType() const {
        return NOTE_OFF;
    }

    virtual void formatTo(std::ostream &out) const;

    virtual EventPtr clone() const {
        return new NoteOff(time, channel, note);
    }
};

// A sequence of midi events.
class Track : public spug::RCBase {
    private:
        typedef std::vector<EventPtr> EventVec;
        EventVec events;

    public:

        // Add a new event.  The event must have a time later than the last
        // event already in the track.
        void add(Event *event);

        EventVec::iterator begin() { return events.begin(); }
        EventVec::iterator end() { return events.end(); }
};

SPUG_RCPTR(Track);

}  // namespace awb

inline std::ostream &operator <<(std::ostream &out, const awb::Event &event) {
    event.formatTo(out);
    return out;
}

#endif
