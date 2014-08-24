#include "event.h"

#include <iostream>

#include <spug/check.h>
#include <spug/Exception.h>

using namespace awb;
using namespace spug;
using namespace std;

namespace {
    void writeVarLen(ostream &out, uint val) {

        // Special case 0.
        if (val == 0) {
            out << static_cast<byte>(0);
            return;
        }

        // Encode the value into an array of bytes.  It's easier to do this
        // from LSB to MSB.
        byte bytes[5];
        int i = 0;
        while (val) {
            byte cur = val & 0x7f;
            val >>= 7;
            if (i != 0) cur |= 0x80;
            bytes[i++] = cur;
        }

        // Now write the byte out in the correct order
        while (i)
            out << bytes[--i];
    }
}

void Event::writeMidiWithTime(byte &status, uint lastTime, ostream &out) const {
    SPUG_CHECK(time >= lastTime,
               "writing event " << *this <<
                " which is earlier than last event " << lastTime
               );
    writeVarLen(out, time - lastTime);
    writeMidi(status, out);
}

void NoteOn::writeMidi(byte &status, ostream &out) const {
    if (status == (0x90 | channel)) {
        out << note << velocity;
    } else {
        status = 0x90 | channel;
        out << static_cast<byte>(0x90 | channel) << note << velocity;
    }
}

void NoteOn::formatTo(ostream &out) const {
    out << "NoteOn(t=" << time << ", ch=" << static_cast<int>(channel) <<
        ", n=" << static_cast<int>(note) <<
        ", v=" << static_cast<int>(velocity) << ")";
}

void NoteOff::writeMidi(byte &status, ostream &out) const {
    if (status == (0x80 | channel)) {
        out << note << velocity;
    } else if (status == (0x90 | channel) && velocity == 0) {
        out << note << velocity;
    } else {
        status = 0x80 | channel;
        out << static_cast<byte>(0x80 | channel) << note << velocity;
    }
}

void NoteOff::formatTo(ostream &out) const {
    out << "NoteOff(t=" << static_cast<int>(time) << ", ch=" <<
        static_cast<int>(channel) << ", n=" << static_cast<int>(note) << ")";
}

void ProgramChange::writeMidi(byte &status, ostream &out) const {
    status = 0xC0 | channel;
    out << status << program;
}

void ProgramChange::formatTo(ostream &out) const {
    out << "ProgramChange(t=" << static_cast<int>(time) << ", ch=" <<
        static_cast<int>(channel) << ", prog=" << static_cast<int>(program) <<
        ")";
}

void Track::add(Event *event) {
    SPUG_CHECK(!events.size() || event->time >= events.back()->time,
               "Adding event " << *event <<
               " which is earlier than the last event on the track (" <<
               *events.back() << ")"
               );
    events.push_back(event);
}

TrackPtr Track::readFromMidi(const byte *data, size_t size) {
    MidiReader reader(data, size);
    return reader.readTrack(0);
}

byte MidiReader::readByte() {
    if (cur < end)
        return *cur++;
    else
        throw Exception("Unexpected end of buffer.");
}

uint MidiReader::readVarLen() {
    uint val = 0;
    byte b = 0x80;
    while (b & 0x80) {
        b = readByte();
        val = val << 7 | (b & 0x7F);
    }
    return val;
}

//    Event readUserEvent() {
//        @assert(false);
//        return null;
//    }

EventPtr MidiReader::readEvent() {
    // If we're out of data, return a null.
    if (cur >= end)
        return 0;

    byte first = readByte();

    // is it a status byte?
    if (first & 0x80) {
        status = first;
        first = readByte();
    }

    byte statusHigh = status & 0xF0;
    byte channel = status & 0xF;
    if (statusHigh == 0x90) {
        byte velocity = readByte();
        if (velocity)
            return new NoteOn(0, channel, first, velocity);
        else
            return new NoteOff(0, channel, first);
    } else if (statusHigh == 0x80) {
        return new NoteOff(0, channel, first, readByte());
    } else if (statusHigh == 0xE0) {
        byte high = readByte();
        cerr << "reading PitchWheel not supported yet" << endl;
        return 0;
//                return new PitchWheel(0, channel, (readByte() << 7) | first);
    } else if (statusHigh == 0xC0) {
        return new ProgramChange(0, channel, first);
    } else if (statusHigh == 0xB0) {
        cerr << "reading ControlChange not supported yet" << endl;
        return 0;
//            return ControlChange(0, channel, first, readByte());
    } else if (status == 0xF0) {
        // sys-ex event
        cerr << "reading SysEx not supported yet" << endl;
        return 0;
//            size := readVarLen();
//            ManagedBuffer tempBuf = {size};
//            // XXX broken! Will ignore the existing buffer.
//            src.read(tempBuf);
//            terminator := readByte();
//            @assert(terminator == 0xF7);
//            return SysEx(0, String(tempBuf, true));
    } else if (status == 0xFF) {
        byte action = first;
        if (action == 0x2F) {
            SPUG_CHECK(readByte() == 0,
                    "End of track event is 0x2f + non-zero"
                    );
            cerr << "reading EndTrack not supported yet." << endl;
            return 0;
//                return EndTrack(0);
        } else {
            return 0;
        }
    } else {
        cerr << "unknown status code: " << static_cast<int>(status) << endl;
        return 0;
//            return readUserEvent();
    }
}

TrackPtr MidiReader::readTrack(const char *name) {
    TrackPtr track = new Track();
    uint t = 0;
    while (cur < end) {
        // read the time
        t += readVarLen();
        EventPtr evt = readEvent();
        if (!evt)
            break;
        evt->time = t;
        track->add(evt.get());
//            if (evt.isa(EndTrack))
//                break;
    }

    return track;
}

std::ostream &operator <<(ostream &out, const Track &track) {
    out << "track {\n";
    for (int i = 0; i < track.size(); ++i) {
        track.get(i)->formatTo(out);
        out << ",\n";
    }
    out << "}\n";
    return out;
}