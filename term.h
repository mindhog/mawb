#ifndef awb_term_h_
#define awb_term_h_

#include <string>

#include "spug/Reactable.h"
#include "spug/Exception.h"

namespace awb {

class JackEngine;

// Terminal interface.
class Term : public spug::Reactable {
    private:
        JackEngine &jackEngine;

        enum Mode {
            KEY_CMD,
            LINE_READ
        } mode;

        std::string lineBuf;

        enum Commands {
            CMD_LOAD,
            CMD_STORE
        } lastCmd;

    public:

        // Define an exception to be thrown when we get a "quit" message.
        SPUG_EXCEPTION(Quit)

        Term(JackEngine &jackEngine);
        ~Term();

        virtual Status getStatus() {
            return readyToRead;
        }

        virtual void handleRead(spug::Reactor &reactor);

        virtual void handleWrite(spug::Reactor &reactor) {
            throw spug::Exception("Term: handleWrite called.");
        }

        virtual void handleError(spug::Reactor &reactor) {
            throw spug::Exception("Term: handleError called.");
        }

        virtual void handleDisconnect(spug::Reactor &reactor) {}

        virtual int fileno() {
            // Standard input.
            return 0;
        }

        // Returns true if standard input is a tty.
        static bool isTTY();
};

} // namespace awb

#endif
