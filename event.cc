#include "event.h"

#include <iostream>

#include <spug/check.h>

using namespace awb;
using namespace std;

void NoteOn::formatTo(std::ostream &out) const {
    out << "NoteOn(t=" << time << ", ch=" << channel << ", n=" << note <<
        ", v=" << velocity << ")";
}

void NoteOff::formatTo(std::ostream &out) const {
    out << "NoteOff(t=" << time << ", ch=" << channel << ", n=" << note
        << ")";
}

void Track::add(Event *event) {
    SPUG_CHECK(!events.size() || event->time >= events.back()->time,
               "Adding event " << *event <<
               " which is earlier than the last event on the track (" <<
               *events.back() << ")"
               );
    events.push_back(event);
}
