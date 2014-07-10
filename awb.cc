#include <iostream>

#include <google/protobuf/io/coded_stream.h>

#include "spug/RCPtr.h"
#include "spug/Reactable.h"
#include "spug/Reactor.h"
#include "spug/Socket.h"

#include "alsa.h"
#include "engine.h"
#include "event.h"
#include "fluid.h"
#include "mawb.pb.h"

namespace spug {
    SPUG_RCPTR(Reactor);
}

using namespace awb;
using namespace google::protobuf::io;
using namespace mawb;
using namespace std;
using namespace spug;

class ConnectionHandler : public Reactable {
    private:
        Socket *socket;
        string outData, inData;
        char buffer[4096];
        Controller &controller;

    public:

        ConnectionHandler(Socket *socket, Controller &controller) :
            socket(socket),
            controller(controller) {
        }

        ~ConnectionHandler() {
            delete socket;
        }

        virtual Status getStatus() {
            return static_cast<Reactable::Status>(
                (outData.size() ? readyToWrite : 0) | readyToRead
            );
        }

        bool processEcho(const string &message) {
            cout << "Echo: " << message << endl;
        }

        void processSetTicks(uint32 ticks) {
            controller.setTicks(ticks);
        }

        void processSetState(SequencerState newState) {
            controller.setState(newState);
        }

        // Processes the message, returns 'true' if the message is so far
        // still viable, false if the reactor should terminate the connection.
        bool processMessage() {
            // Make sure we have at least 4 bytes, which will give us the
            // length of the payload.
            while (inData.size() >= 4) {

                // Get the size of the data.
                CodedInputStream src(
                    reinterpret_cast<const uint8 *>(inData.data()),
                    inData.size()
                );
                uint32 size;
                if (!src.ReadLittleEndian32(&size))
                    return false;

                // Make sure we have enough data.
                if (inData.size() < size + 4)
                    return true;

                // Process all of the messages.
                mawb::RPC rpc;
                rpc.ParseFromString(inData.substr(4));
                if (rpc.echo_size()) {
                    for (int i = 0; i < rpc.echo_size(); ++i)
                        processEcho(rpc.echo(i));
                }

                if (rpc.set_ticks_size()) {
                    for (int i = 0; i < rpc.set_ticks_size(); ++i)
                        processSetTicks(rpc.set_ticks(i));
                }

                if (rpc.has_change_sequencer_state())
                    processSetState(rpc.change_sequencer_state());

                // Truncate the used portion of the buffer.
                inData = inData.substr(size);
            }
            return true;
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
        Controller &controller;

    public:
        Listener(int port, Controller &controller) :
            socket(port),
            controller(controller) {

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
            reactor.addReactable(
                new ConnectionHandler(socket.acceptAlloc(), controller)
            );
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
        TimeMaster timeMaster;
        timeMaster.setPPB(96);
        timeMaster.setBPM(120);

        // Create the sequencer.
        Sequencer sequencer(SND_SEQ_OPEN_INPUT | SND_SEQ_OPEN_OUTPUT, 0);
        Port readport = sequencer.makeReadPort("mawb");
        Port writeport = sequencer.makeWritePort("mawb");

        // Set up the input chain: Alsa port -> InputDispatcher ->
        // FluidSynthDispatcher.
        // All of this stuff should be set up from the persistent state or
        // from the RPC interface.
        FluidSynthDispatcherPtr fs = new FluidSynthDispatcher();
        fs->loadFont("/usr/share/sounds/sf2/FluidR3_GM.sf2", true);
        InputDispatcherPtr dispatcher =
            new InputDispatcher(&timeMaster, 0, fs.get());

        ReactorPtr reactor = Reactor::createReactor();
        reactor->addReactable(new AlsaReactable(sequencer, dispatcher.get()));

        // Create the controller and add the input.
        Controller controller(*reactor, timeMaster);
        controller.addInput(dispatcher.get());

        // Create the RPC listener.
        reactor->addReactable(new Listener(8193, controller));

        cerr << "AWB daemon started." << endl;
        reactor->run();
    } catch (const spug::Exception &ex) {
        cerr << "Got an error: " << ex << endl;
    }
}
