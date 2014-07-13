
#include <iomanip>
#include <iostream>
#include <sstream>

#include "event.h"

using namespace awb;
using namespace std;

#define FAIL(text) { cerr << text << endl; return false; }
#define RUN_TEST(testFunc) \
    { \
        cerr << #testFunc "..." << flush; \
        bool rc = testFunc(); \
        if (rc) \
            cerr << "\033[32mOK\033[36m" << endl; \
        else \
            cerr << "\033[31mFAILED\033[36m" << endl; \
    }

struct Hex {
    const string &data;
    Hex(const string &data) : data(data) {}
};

ostream &operator <<(ostream &out, const Hex &obj) {
    out << "[";
    for (int i = 0; i < obj.data.size(); ++i) {
        unsigned int val = obj.data[i] & 0xff;
        if (val < 16)
            out << hex << "0" << val << " ";
        else
            out << hex << val << " ";
    }
    out << "]";
    return out;
}

bool testStatusCollapsing() {
    NoteOn n0(0, 3, 1, 2);
    NoteOn n1(0, 3, 3, 4);

    ostringstream out;
    byte status = 0;
    n0.writeMidi(status, out);
    n1.writeMidi(status, out);
    if (out.str() != "\x93\x01\x02\x03\x04")
        FAIL("status collapsing failed, got " << Hex(out.str()));

    MidiReader reader(reinterpret_cast<const byte *>(out.str().data()),
                      out.str().size()
                      );
    EventPtr e = reader.readEvent();
    if (!e)
        FAIL("Failed to read back first event.");
    if (e->getType() != Event::NOTE_ON)
        FAIL("First event, expected note, got " << *e);
    NoteOnPtr n = NoteOnPtr::rcast(e);
    if (n->note != 1 || n->velocity != 2)
        FAIL("First event, expected note on n=1, v=2, got " << *e);

    e = reader.readEvent();
    if (!e)
        FAIL("Failed to read back second event.");
    if (e->getType() != Event::NOTE_ON)
        FAIL("Second event, expected note, got " << *e);
    n = NoteOnPtr::rcast(e);
    if (!n || n->note != 3 || n->velocity != 4)
        FAIL("Second event, expected note on n=3, v=4, got " << *e);

    e = reader.readEvent();
    if (e)
        FAIL("Failed at end of buffer, expected null, got " << *e);

    return true;
}

bool testNoStatusCollapsing() {
    NoteOn n0(0, 3, 1, 2);
    NoteOn n1(0, 4, 3, 4);

    ostringstream out;
    byte status = 0;
    n0.writeMidi(status, out);
    n1.writeMidi(status, out);
    if (out.str() != "\x93\x01\x02\x94\x03\x04")
        FAIL("no status collapsing failed, got " << Hex(out.str()));

    MidiReader reader(reinterpret_cast<const byte *>(out.str().data()),
                      out.str().size()
                      );

    EventPtr e = reader.readEvent();
    if (!e)
        FAIL("Failed to read back first event.");
    if (e->getType() != Event::NOTE_ON)
        FAIL("First event, expected note, got " << *e);
    NoteOnPtr n = NoteOnPtr::rcast(e);
    if (!n || n->note != 1 || n->velocity != 2)
        FAIL("First event, expected note on n=1, v=2, got " << *e);

    e = reader.readEvent();
    if (!e)
        FAIL("Failed to read back second event.");
    if (e->getType() != Event::NOTE_ON)
        FAIL("Second event, expected note, got " << *e);
    n = NoteOnPtr::rcast(e);
    if (!n || n->note != 3 || n->velocity != 4)
        FAIL("Second event, expected note on n=3, v=4, got " << *e);

    e = reader.readEvent();
    if (e)
        FAIL("Failed at end of buffer, expected null, got " << *e);

    return true;
}

bool testNoteOffCollapsing() {
    NoteOn n0(0, 3, 1, 2);
    NoteOff n1(0, 3, 1);

    ostringstream out;
    byte status = 0;
    n0.writeMidi(status, out);
    n1.writeMidi(status, out);
    if (out.str() != string("\x93\x01\x02\x01\x00", 5))
        FAIL("no status collapsing failed, got " << Hex(out.str()));

    MidiReader reader(reinterpret_cast<const byte *>(out.str().data()),
                      out.str().size()
                      );

    EventPtr e = reader.readEvent();
    if (!e)
        FAIL("Failed to read back first event.");
    if (e->getType() != Event::NOTE_ON)
        FAIL("First event, expected note, got " << *e);
    NoteOnPtr n = NoteOnPtr::rcast(e);
    if (!n || n->note != 1 || n->velocity != 2)
        FAIL("First event, expected note on n=1, v=2, got " << *e);

    e = reader.readEvent();
    if (!e)
        FAIL("Failed to read back second event.");
    if (e->getType() != Event::NOTE_OFF)
        FAIL("Second event, expected note, got " << *e);
    NoteOffPtr n2 = NoteOffPtr::rcast(e);
    if (!n2 || n2->note != 1 || n2->velocity != 0)
        FAIL("Second event, expected note off n=1, v=0, got " << *e);

    e = reader.readEvent();
    if (e)
        FAIL("Failed at end of buffer, expected null, got " << *e);

    return true;
}

int main(int args, const char **argv) {
    RUN_TEST(testStatusCollapsing);
    RUN_TEST(testNoStatusCollapsing);
    RUN_TEST(testNoteOffCollapsing);
}
