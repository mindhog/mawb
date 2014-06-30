#ifndef awb_alsa_h_
#define awb_alsa_h_

#include <alsa/asoundlib.h>
#include "spug/Exception.h"
#include "spug/Reactable.h"
#include "spug/Reactor.h"
#include "spug/RCPtr.h"
#include "spug/StringFmt.h"

#include "engine.h"

namespace awb {

SPUG_RCPTR(Event);

class Port {
    private:
        snd_seq_t *seq;
        int port;

    public:
        Port(snd_seq_t *seq, int port) : seq(seq), port(port) {}

        // Connect to another midi port as specified by a client and port
        // number (e.g. "129:0").
        void connectTo(int otherClient, int otherPort) {
            snd_seq_connect_to(seq, port, otherClient, otherPort);
        }

        // Send an event to the port.
        void send(const Event &event);
};

// The sequencer must remain in existence for as long as all of its ports do.
class Sequencer {
    private:
        snd_seq_t *seq;

    public:
        /**
         * streams is SND_SEQ_OPEN_INPUT | SND_SEQ_OPEN_OUTPUT.
         * mode is usually zero.
         */
        Sequencer(int streams, int mode) {
            if (snd_seq_open(&seq, "default", streams, mode))
                throw spug::Exception("Failed to open sequencer.");
        }

        ~Sequencer() {
            snd_seq_close(seq);
        }

    Port makeReadPort(const char *portName) {
        return Port(seq,
                    snd_seq_create_simple_port(
                        seq,
                        portName,
                        SND_SEQ_PORT_CAP_READ | SND_SEQ_PORT_CAP_SUBS_READ,
                        SND_SEQ_PORT_TYPE_MIDI_GENERIC
                    )
        );
    }

    Port makeWritePort(const char *portName) {
        return Port(seq,
                    snd_seq_create_simple_port(
                        seq,
                        portName,
                        SND_SEQ_PORT_CAP_WRITE | SND_SEQ_PORT_CAP_SUBS_WRITE,
                        SND_SEQ_PORT_TYPE_MIDI_GENERIC
                    )
        );
    }

    // Get the next event from the sequencer.
    EventPtr getEvent() const;

    int handle();

};

class AlsaReactable : public spug::Reactable {
    private:
        Sequencer &seq;
        EventDispatcher *dispatcher;

    public:
        // Does not take ownership of dispatcher, the caller must manage this.
        AlsaReactable(Sequencer &seq, EventDispatcher *dispatcher) :
            seq(seq),
            dispatcher(dispatcher) {
        }

        virtual Status getStatus() {
            return readyToRead;
        }

        virtual void handleRead(spug::Reactor &reactor);

        virtual void handleWrite(spug::Reactor &reactor) {
            throw spug::Exception("AlsaReactable::handleWrite called");
        }

        virtual void handleError(spug::Reactor &reactor) {
            throw spug::Exception("AlsaReactable::handleError called");
        }

        virtual void handleDisconnect(spug::Reactor &reactor) {}

        virtual int fileno() {
            return seq.handle();
        }
};

} // namespace awb

#endif
