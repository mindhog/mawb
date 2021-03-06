
#include "alsa.h"

#include "spug/Exception.h"
#include "event.h"

using namespace awb;
using namespace spug;
using namespace std;

void Port::send(const Event &event) {
    snd_seq_event_t e;
    e.source.port = port;
    e.dest.port = SND_SEQ_ADDRESS_UNKNOWN;
    e.queue = SND_SEQ_QUEUE_DIRECT;

    switch (event.getType()) {
        case Event::NOTE_ON: {
            const NoteOn &noteOn = static_cast<const NoteOn &>(event);
            snd_seq_ev_set_noteon(&e, noteOn.channel, noteOn.note,
                                noteOn.velocity
                                );
            break;
        }
        case Event::NOTE_OFF: {
            const NoteOff &noteOff = static_cast<const NoteOff &>(event);
            snd_seq_ev_set_noteoff(&e, noteOff.channel, noteOff.note,
                                   noteOff.velocity
                                   );
            break;
        }
        case Event::PROGRAM_CHANGE: {
            const ProgramChange &pc =
                static_cast<const ProgramChange &>(event);
            snd_seq_ev_set_pgmchange(&e, pc.channel, pc.program);
            break;
        }
        default:
            throw Exception(SPUG_FSTR("Can't send event " <<
                                      event << " to alsa (event type "
                                      " not implemented."));
    }

    snd_seq_event_output(seq, &e);
    snd_seq_drain_output(seq);
}

EventPtr Sequencer::getEvent() const {
    snd_seq_event_t *alsaEvent;
    snd_seq_event_input(seq, &alsaEvent);
    switch (alsaEvent->type) {
        case SND_SEQ_EVENT_NOTEON: {
            snd_seq_ev_note_t &note = alsaEvent->data.note;
            return new NoteOn(0, note.channel, note.note, note.velocity);
        }
        case SND_SEQ_EVENT_NOTEOFF: {
            snd_seq_ev_note_t &note = alsaEvent->data.note;
            return new NoteOff(0, note.channel, note.note);
        }
        case SND_SEQ_EVENT_PGMCHANGE: {
            snd_seq_ev_ctrl_t &ctrl = alsaEvent->data.control;
            return new ProgramChange(0, ctrl.channel, ctrl.value);
        }
        default:
            return 0;
//            throw Exception(SPUG_FSTR("Unknown input event type " <<
//                                      alsaEvent->type
//                                      )
//                            );
    }
}

bool Sequencer::hasEvent() const {
    return snd_seq_event_input_pending(seq, 1);
}

int Sequencer::handle() {
    pollfd pfds;
    int rc = snd_seq_poll_descriptors(seq, &pfds, 1, POLLIN | POLLOUT);
    if (rc != 1)
        throw Exception("Failed to get poll descriptors.");
    return pfds.fd;
}

void AlsaReactable::handleRead(spug::Reactor &reactor) {
    while (seq.hasEvent()) {
        EventPtr event = seq.getEvent();
        if (event)
            dispatcher->onEvent(event.get());
        else
            cerr << "got null event" << endl;
    }
}
