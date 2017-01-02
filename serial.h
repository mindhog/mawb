#ifndef awb_serial_h_
#define awb_serial_h_

#include <spug/Reactable.h>
#include <spug/Exception.h>

namespace awb {

class JackEngine;

/*
    Initialize the deka-pedal like this:

        stty -F /dev/ttyACM0 cs8 115200 ignbrk -brkint -icrnl -imaxbel -opost \
            -onlcr -isig -icanon -iexten -echo -echoe -echok -echoctl -echoke \
            noflsh -ixon -crtscts
*/

// Serial port interface.  This should actually work with any character
// device, though it is currently fairly hard-wired to the deka-pedal.
class Serial : public spug::Reactable {
    private:
        int fd;
        JackEngine &jackEngine;

    public:
        Serial(int fd, JackEngine &jackEngine) :
            fd(fd),
            jackEngine(jackEngine) {
        }

        virtual Status getStatus() {
            return readyToRead;
        }

        virtual void handleRead(spug::Reactor &reactor);

        virtual void handleWrite(spug::Reactor &reactor) {
            throw spug::Exception("Serial: handleWrite called.");
        }

        virtual void handleError(spug::Reactor &reactor) {
            throw spug::Exception("Serial: handleError called.");
        }

        virtual void handleDisconnect(spug::Reactor &reactor) {}

        virtual int fileno() {
            // Standard input.
            return fd;
        }
};

} // namespace awb

#endif
