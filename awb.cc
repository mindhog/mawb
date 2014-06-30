#include <iostream>

#include "spug/RCPtr.h"
#include "spug/Reactable.h"
#include "spug/Reactor.h"
#include "spug/Socket.h"

#include "alsa.h"
#include "engine.h"

namespace spug {
    SPUG_RCPTR(Reactor);
}

using namespace awb;
using namespace std;
using namespace spug;

class ConnectionHandler : public Reactable {
    private:
        Socket *socket;
        string outData, inData;
        char buffer[4096];

    public:

        ConnectionHandler(Socket *socket) : socket(socket) {}

        ~ConnectionHandler() {
            delete socket;
        }

        virtual Status getStatus() {
            return static_cast<Reactable::Status>(
                (outData.size() ? readyToWrite : 0) | readyToRead
            );
        }

        void processMessage() {
            cerr << "got data: " << inData << endl;
            inData = "";
        }

        virtual void handleRead(Reactor &reactor) {
            int rc = socket->recv(buffer, sizeof(buffer));
            if (rc == 0) {
                // shutdown the connection.
                reactor.removeReactable(this);
            } else if (rc > 0) {
                inData.append(buffer, rc);
                processMessage();
            } else {
                cerr << "Error on connection <xxx need connection info>" <<
                    endl;
            }
        }

        virtual void handleWrite(Reactor &reactor) {
            int rc = socket->send(outData.data(), outData.size());
            if (rc > 0)
                outData = outData.substr(rc);
            else if (rc < 0)
                cerr << "Error on write to <need connection info>" << endl;
        }

        virtual void handleError(Reactor &reactor) {
            cerr << "handling an error for <need connection info>" << endl;
        }

        virtual void handleDisconnect(Reactor &reactor) {
            reactor.removeReactable(this);
        }

        /**
         * Returns the file descriptor associated with the reactable.
         */
        virtual int fileno() {
            return socket->handle();
        }
};

class Listener : public Reactable {
    private:
        Socket socket;

    public:
        Listener(int port) : socket(port) {
            socket.listen(5);
        }

        virtual Status getStatus() {
            return readyToRead;
        }

        /**
         * Called when the reactor detects that the reactable is ready to read.
         * The implementation should perform a read on the underlying file
         * descriptor.
         */
        virtual void handleRead(Reactor &reactor) {
            reactor.addReactable(new ConnectionHandler(socket.acceptAlloc()));
        }

        /**
         * Called when the reactor detects that the reactable is ready to
         * write.  The implementation should perform a write on the underlying
         * file descriptor.
         */
        virtual void handleWrite(Reactor &reactor) {}

        /**
         * Called when the reactor detects an error condition on the file
         * descriptor.
         */
        virtual void handleError(Reactor &reactor) {
            cerr << "Listener got an error!" << endl;
        }

        /**
         * Called when the rector detects that the file descriptor has been
         * disconnected.
         */
        virtual void handleDisconnect(Reactor &reactor) {
            cerr << "listener disconnected" << endl;
            reactor.removeReactable(this);
        }

        /**
         * Returns the file descriptor associated with the reactable.
         */
        virtual int fileno() {
            return socket.handle();
        }
};

int main(int argc, const char **argv) {
    try {
        // Create the sequencer.
        Sequencer sequencer(SND_SEQ_OPEN_INPUT | SND_SEQ_OPEN_OUTPUT, 0);
        DebugDispatcher dispatcher;

        Port readport = sequencer.makeReadPort("mawb");
        Port writeport = sequencer.makeWritePort("mawb");

        ReactorPtr reactor = Reactor::createReactor();
        reactor->addReactable(new Listener(8193));
        reactor->addReactable(new AlsaReactable(sequencer, &dispatcher));

        cerr << "AWB daemon started." << endl;
        reactor->run();
    } catch (const spug::Exception &ex) {
        cerr << "Got an error: " << ex << endl;
    }
}
