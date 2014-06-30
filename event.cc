#include "event.h"

using namespace awb;

void NoteOn::formatTo(std::ostream &out) const {
    out << "NoteOn(t=" << time << ", ch=" << channel << ", n=" << note <<
        ", v=" << velocity << ")";
}

void NoteOff::formatTo(std::ostream &out) const {
    out << "NoteOff(t=" << time << ", ch=" << channel << ", n=" << note
        << ")";
}

