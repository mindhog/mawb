#include <fstream>
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
#include "jackengine.h"
#include "mawb.pb.h"
#include "serial.h"
#include "term.h"

namespace spug {
    SPUG_RCPTR(Reactor);
}

using namespace awb;
using namespace google::protobuf::io;
using namespace google::protobuf;
using namespace mawb;
using namespace std;
using namespace spug;

class ConnectionHandler : public Reactable {
    private:
        Socket *socket;
        string outData, inData;
        char buffer[4096];
        Controller &controller;
        JackEngine &jackEngine;

    public:

        ConnectionHandler(Socket *socket, Controller &controller,
                          JackEngine &jackEngine
                          ) :
            socket(socket),
            controller(controller),
            jackEngine(jackEngine) {
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

        void processSetInitialState(const SetInitialState &msg) {
            EventDispatcherPtr disp =
                controller.getDispatcher(msg.dispatcher());
            if (disp) {
                TrackPtr track = Track::readFromMidi(
                    reinterpret_cast<const byte *>(msg.events().data()),
                    msg.events().size()
                );
                disp->initialState = msg.events();
                disp->sendEvents(*track);
            } else {
                cerr << "Invalid dispatcher: " << msg.dispatcher() << endl;
            }
        }

        void processSetState(SequencerState newState) {
            controller.setState(newState);
        }

        void processChangeJackState(const ChangeJackStateRequest &newState) {
            switch (newState.state()) {
                case IDLE:
                    jackEngine.endRecord();
                    jackEngine.endPlay();
                    break;
                case RECORD:
                    jackEngine.startRecord(newState.channel());
                    break;
                case PLAY:
                    jackEngine.endRecord();
                    jackEngine.startPlay();
                    break;
                case LATCHED_RECORD:
                    // Not sure what to do about this one.
                default:
                    cerr << "Unrecognized state " << newState.state() << endl;
                    break;
            }
        }

        void processClearState(const ClearStateRequest &clearState) {
            jackEngine.clear();
        }

        void processShutdown(const ShutdownRequest &shutdown) {
            throw Term::Quit();
        }

        void processSaveState(const string &filename) {
//            controller.saveState(filename);
            ofstream dst(filename);
            jackEngine.store(dst);
            cerr << "\r\nsaved file " << filename << "\r" << endl;
        }

        void processChangeSection(const ChangeSectionRequest &changeSection) {
            // TODO: deal with section indexes.
            if (changeSection.sectionindex() == -1)
                jackEngine.startPrevSection();
            else
                jackEngine.startNextSection();
        }

        void processNewSection(const NewSectionRequest &newSection) {
            jackEngine.startNewSection();
        }

        void processChangeChannelAttrs(const ChangeChannelAttrs &changeAttrs) {
            if (changeAttrs.has_sticky())
                jackEngine.setSticky(changeAttrs.channel(),
                                     changeAttrs.sticky()
                                     );
        }

        // Serialize the message to the output buffer to be sent as soon as
        // possible.
        void sendMessage(Message &msg) {
            // Serialize the message.
            string serializedMsg;
            msg.SerializeToString(&serializedMsg);

            // Stick the current output buffer into the temporary.
            ostringstream temp;
            temp << outData;

            // Serialize the size.
            size_t size = serializedMsg.size();
            temp << static_cast<byte>(size & 0xff)
                 << static_cast<byte>((size >> 8) & 0xff)
                 << static_cast<byte>((size >> 16) & 0xff)
                 << static_cast<byte>(size >> 24);

            // Tack on the message and add it to the buffer to be sent.
            temp << serializedMsg;
            outData = temp.str();
        }

        void processLoadState(const LoadState &message, Response *resp) {
//            Project project = controller.loadState(message.filename());
//
//            if (resp)
//                resp->mutable_project()->CopyFrom(project);
            ifstream src(message.filename());
            jackEngine.load(src);
            cerr << "\r\nloaded file " << message.filename() << "\r" << endl;
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
                if (inData.size() < size + 4) {
                    cerr << "Incomplete message, waiting for " << size <<
                        ".\r" << endl;
                    return true;
                }

                // Process all of the requests in the RPC message.
                mawb::RPC rpc;
                rpc.ParseFromString(inData.substr(4));

                // If there is a message id, create a response.
                Response *resp = 0;
                if (rpc.has_msg_id()) {
                    resp = new Response();
                    resp->set_msg_id(rpc.msg_id());
                }

                if (rpc.echo_size()) {
                    for (int i = 0; i < rpc.echo_size(); ++i)
                        processEcho(rpc.echo(i));
                }

                if (rpc.set_ticks_size()) {
                    for (int i = 0; i < rpc.set_ticks_size(); ++i)
                        processSetTicks(rpc.set_ticks(i));
                }

                if (rpc.set_initial_state_size()) {
                    for (int i = 0; i < rpc.set_initial_state_size(); ++i)
                        processSetInitialState(rpc.set_initial_state(i));
                }

                if (rpc.has_set_input_params()) {
                    const SetInputParams &inputParams = rpc.set_input_params();
                    if (inputParams.has_output_channel())
                        controller.getInputDispatcher()->setOutputChannel(
                            inputParams.output_channel()
                        );
                }

                if (rpc.has_save_state())
                    processSaveState(rpc.save_state());

                if (rpc.has_load_state())
                    processLoadState(rpc.load_state(), resp);

                if (rpc.has_add_track()) {
                    controller.addTrack(rpc.add_track());
                }

                // We do this after the state change events so a client can
                // add a "play" to setup.
                if (rpc.has_change_sequencer_state())
                    processSetState(rpc.change_sequencer_state());

                if (rpc.has_change_jack_state())
                    processChangeJackState(rpc.change_jack_state());

                if (rpc.has_clear_state())
                    processClearState(rpc.clear_state());

                if (rpc.has_shutdown())
                    processShutdown(rpc.shutdown());

                if (rpc.has_change_section())
                    processChangeSection(rpc.change_section());

                if (rpc.has_new_section())
                    processNewSection(rpc.new_section());

                if (rpc.has_change_channel_attrs())
                    processChangeChannelAttrs(rpc.change_channel_attrs());

                // Truncate the used portion of the buffer.
                inData = inData.substr(size + 4);

                // Send the response, if requested.
                if (resp) {
                    sendMessage(*resp);
                    delete resp;
                }

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
        JackEngine &jackEngine;

    public:
        Listener(int port, Controller &controller, JackEngine &jackEngine) :
            socket(port),
            controller(controller),
            jackEngine(jackEngine) {

            socket.listen(5);
            socket.setReusable(true);
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
                new ConnectionHandler(socket.acceptAlloc(), controller,
                                      jackEngine
                                      )
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

/**
 * A streambuf that just discards all of its input.
 */
class NullStreambuf : public streambuf {
    virtual int overflow(int c = EOF) {
        return !EOF;
    }

    virtual int sync() {
        return EOF;
    }

    virtual int underflow() {
        return EOF;
    }
};

int main(int argc, const char **argv) {
    // Making this live outside of the try catch because I haven't figured
    // out how to shut it down cleanly during an exception.
    FluidSynthDispatcherPtr fs;

    bool enablePedal = false;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "-p")) {
            enablePedal = true;
        } else if (!strcmp(argv[i], "-q")) {
            // Make cout and cerr inert.
            cerr.rdbuf(new NullStreambuf());
            cout.rdbuf(new NullStreambuf());
        } else {
            cerr << "Unknown argument: " << argv[i] << endl;
        }
    }

    try {
        TimeMaster timeMaster;
        timeMaster.setPPB(96);
        timeMaster.setBPM(120);

        // Create the sequencer.
        Sequencer sequencer(SND_SEQ_OPEN_INPUT | SND_SEQ_OPEN_OUTPUT, 0);
        Port readport = sequencer.makeReadPort("mawb_out");
        Port writeport = sequencer.makeWritePort("mawb_in");

        // Set up the input chain: Alsa port -> InputDispatcher ->
        // FluidSynthDispatcher.
        // All of this stuff should be set up from the persistent state or
        // from the RPC interface.
        fs = new FluidSynthDispatcher();
        fs->loadFont("/usr/share/sounds/sf2/FluidR3_GM.sf2", true);
        InputDispatcherPtr dispatcher =
            new InputDispatcher(&timeMaster, 0, fs.get());

        ReactorPtr reactor = Reactor::createReactor();
        reactor->addReactable(new AlsaReactable(sequencer, dispatcher.get()));

        // Create the Jack engine and start it moving.
        JackEngine *jackEng = JackEngine::create("mawb");
        jackEng->startPlay();

        // Create the controller and register the input and fluid dispatcher
        // with the controller.
        Controller controller(*reactor, timeMaster, *jackEng);
        controller.addInput(dispatcher.get());
        controller.setDispatcher("fluid", fs.get());

        // Create the RPC listener.
        reactor->addReactable(new Listener(8193, controller, *jackEng));

        // If we're on a TTY, start the terminal interface.
        if (Term::isTTY()) {
            cerr << "Starting terminal interface..." << endl;
            reactor->addReactable(new Term(*jackEng));
        }

        if (enablePedal) {
            // Open the deka-pedal.
            int pedal = open("/dev/ttyACM0", O_RDONLY);
            if (pedal != -1) {
                cerr << "Adding pedal interface\r" << endl;
                reactor->addReactable(new Serial(pedal, *jackEng));
            }
        }

        cerr << "AWB daemon started.\r" << endl;
        reactor->run();
    } catch (const Term::Quit &ex) {
        cerr << "Shut down from terminal." << endl;
    } catch (const spug::Exception &ex) {
        cerr << "Got an error: " << ex << endl;
    }
}
