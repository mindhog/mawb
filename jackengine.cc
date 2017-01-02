#include "jackengine.h"

#include <assert.h>
#include <jack/jack.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>

#include <atomic>
#include <iostream>
#include <vector>

#include "wavetree.h"

using namespace awb;
using namespace std;

static int jack_callback(jack_nframes_t nframes, void *arg) {
    reinterpret_cast<JackEngine*>(arg)->process(nframes);
    return 0;
}

namespace {

struct Channel {
    WaveTree *data;

    // "enabled" means that a channel is playing audio.
    bool enabled;

    // The end position of the data stored in the channel.
    int end;

    // The position at the time we began recording the current channel (this
    // is only meaningful when the channel is being recorded)
    int startPos;

    // The position when we started recording 'data'.  This is added to the
    // position when we look up buffers from audio data during replay.
    int offset;

    Channel(Channel &&other) {
        take(other);
    }

    // Create a channel and allocate an initial buffer.
    Channel() :
        data(new WaveTree()),
        enabled(true),
        end(0),
        startPos(0),
        offset(0) {
    }

    ~Channel() {
        delete data;
    }

    Channel &operator =(Channel &&other) {
        take(other);
        return *this;
    }

    void take(Channel &other) {
        data = other.data;
        enabled = other.enabled;
        end = other.end;
        startPos = other.startPos;
        offset = other.offset;
        other.data = 0;
    }

    // Returns a buffer for writing at the given position, creating it if
    // necessary.
    // The buffer position is not modified by offset or end.
    WaveBuf *getWriteBuffer(int pos) {
        return data->get(pos * 2, true);
    }

    // Returns a buffer for reading at the given position, null if no buffer
    // has been stored there.
    WaveBuf *getReadBuffer(int pos) {
        cerr << pos;
        pos = (end ? pos % end : pos) + offset;
        cerr << " (" << pos << ") " << flush;

        return data->get(pos * 2, false);
    }

    Channel(const Channel &other) = delete;
};

enum Command {
    // clear all channels, reset to a pristine state.
    clearCmd,

    // Don't do anything.
    noopCmd,
};

class JackEngineImpl : public JackEngine {
    public:

        jack_client_t *client;
        jack_port_t *in1, *in2, *out1, *out2;
        size_t arenaSize;
        vector<Channel> channels;
        atomic_int recordChannel, playing;
        atomic_int pos;

        // Commands sent from other threads.
        atomic<Command> command;

        // The record mode.
        atomic<RecordMode> recordMode;

        // The end sample position.  At this point, we start looping.
        int end;

        // Set to true when we process a buffer while recording.  This lets us
        // keep track of the state changes as we go from recording to not.
        bool recording;

        // The last channel we were recording on.
        int lastRecordChannel;

        // True if the engine has been initialized.
        bool initialized;

        JackEngineImpl(const char *name) :
                client(0),
                recordChannel(-1),
                playing(0),
                pos(0),
                command(noopCmd),
                end(0),
                recordMode(expand),
                recording(false),
                lastRecordChannel(-1),
                initialized(false) {
            jack_status_t status;
            client = jack_client_open(name, static_cast<jack_options_t>(0),
                                      &status);
            jack_set_process_callback(client, jack_callback, this);
            in1 = jack_port_register(client, "in_1",
                                     JACK_DEFAULT_AUDIO_TYPE,
                                     JackPortIsInput,
                                     4096
                                     );
            in2 = jack_port_register(client, "in_2",
                                     JACK_DEFAULT_AUDIO_TYPE,
                                     JackPortIsInput,
                                     4096
                                     );
            out1 = jack_port_register(client, "out_1",
                                      JACK_DEFAULT_AUDIO_TYPE,
                                      JackPortIsOutput,
                                      4096
                                      );
            out2 = jack_port_register(client, "out_2",
                                      JACK_DEFAULT_AUDIO_TYPE,
                                      JackPortIsOutput,
                                      4096
                                      );
            jack_activate(client);
        }
};

// Audio sample rate.
int framesPerSecond = 44100;

} // anon namespace

JackEngine *JackEngine::create(const char *name) {
    return new JackEngineImpl(name);
}

void JackEngine::process(unsigned int nframes) {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    int &end = impl->end;

    // Initialize if necessary.
    if (!impl->initialized) {
        WaveTree::setBufferSize(nframes * 2);
        impl->initialized = true;
    } else {
        assert(nframes * 2 == WaveTree::getBufferSize());
    }

    // Process a command.
    Command command = impl->command.load(memory_order_relaxed);
    switch (command) {
        case clearCmd:
            impl->channels.clear();
            impl->command.store(noopCmd, memory_order_relaxed);
            impl->end = 0;
            impl->playing.store(true, memory_order_relaxed);
            break;
        case noopCmd:
            break;
        default:
            assert(false && "Unknown command received.");
    }

    int pos = impl->pos.load(memory_order_relaxed);

    // Get all of the buffers.
    float *in1Buf = reinterpret_cast<float *>(
        jack_port_get_buffer(impl->in1, nframes));
    float *in2Buf = reinterpret_cast<float *>(
        jack_port_get_buffer(impl->in2, nframes));
    float *out1Buf = reinterpret_cast<float *>(
        jack_port_get_buffer(impl->out1, nframes));
    float *out2Buf = reinterpret_cast<float *>(
        jack_port_get_buffer(impl->out2, nframes));

    // Process input.
    int recordChannel = impl->recordChannel.load(memory_order_relaxed);
    if (recordChannel != -1) {
        // If we weren't previously recording, reset the record position to
        // zero.
        bool startedRecording = false;
        if (!impl->recording) {
            if (impl->channels.empty())
                pos = 0;
            impl->recording = true;
            impl->lastRecordChannel = recordChannel;
            startedRecording = true;
        }

        // Allocate a new channel if necessary.
        Channel *channel;
        if (recordChannel >= impl->channels.size()) {
            impl->channels.push_back(Channel());
            channel = &impl->channels.back();
            if (recordChannel != impl->channels.size() - 1) {
                recordChannel = impl->channels.size() - 1;
                impl->recordChannel.store(recordChannel, memory_order_relaxed);
                impl->lastRecordChannel = recordChannel;
            }
        } else {
            channel = &impl->channels[recordChannel];
        }

        // If we just started recording, store the start pos.
        if (startedRecording)
            channel->startPos = pos;

        // Record the buffer.
        WaveBuf *buf = channel->getWriteBuffer(pos);;
        for (int i = 0; i < nframes; ++i) {
            out1Buf[i] = buf->buffer[i * 2] = in1Buf[i];
            out2Buf[i] = buf->buffer[i * 2 + 1] = in2Buf[i];
        }

    } else {
        // Not recording, just do a pass-through.
        for (int i = 0; i < nframes; ++i) {
            out1Buf[i] = in1Buf[i];
            out2Buf[i] = in2Buf[i];
        }

        // If we were recording but are no longer, flip the flag and do
        // whatever other finalization we need to.
        if (impl->recording) {
            impl->recording = false;

            Channel &channel = impl->channels[impl->lastRecordChannel];

            // Store the end of the record channel.
            if (impl->recordMode == JackEngineImpl::expand && end) {

                // If we started recording very shortly before the end of the
                // span, we assume that we want to line up with the start of
                // the span so set the offset accordingly.
                cerr << "frame begins at " <<
                    ((end - channel.startPos) * 100 / end) <<
                    " percent (" <<
                    (float(end - channel.startPos) / framesPerSecond) <<
                    "/" << (float(end) / framesPerSecond) <<
                    " seconds) before end of span\r" << endl;
                if (end - channel.startPos < framesPerSecond / 10)
                    channel.offset = end;
                else
                    channel.offset = 0;

                // If we exceeded the end by more than a tenth of a second
                // (human error) in expand mode, we want to adjust the end to
                // be the first multiple of end that is greater than the
                // current pos.
                if (pos - channel.offset > end + framesPerSecond / 10) {
                    int localPos = pos - channel.offset;
                    int multiple = localPos / end;

                    // We normally want to increment the multiple because,
                    // for example, for a new span that is 1.5 times the
                    // length of the old span we'd get a multiple of 1 and
                    // we'd want a multiple of 2. But only do this if we
                    // exceeed the last boundary by the "jitter delay" (so,
                    // for example, 1.1 seconds would still count as just 1).
                    if (localPos - end * multiple > framesPerSecond / 10)
                        ++multiple;
                    localPos = end * multiple;

                    end = localPos;
                    cerr << "changed end to " << end << " (multiple of " <<
                        multiple << ")\r" << endl;
                }
            }

            // if we finished recording the first channel, store the end.
            if (!end) {
                end = pos;
                impl->pos.store(0, memory_order_relaxed);
            }

            channel.end = end;
            cerr << "recorded channel {offset: " << channel.offset <<
                ", end = " << channel.end << "} engine end = " << end <<
                "\r" << endl;
        }
    }

    // Playback.
    bool playing = impl->playing.load(memory_order_relaxed);
    if (playing) {
        int channelIndex = -1;
        for (Channel &channel : impl->channels) {
            ++channelIndex;
            if (channel.enabled && recordChannel != channelIndex) {
                assert(channel.end);
                cerr << channelIndex << ": ";
                WaveBuf *buf = channel.getReadBuffer(pos);
                if (!buf) continue;

                for (int i = 0; i < nframes; ++i) {
                    out2Buf[i] += buf->buffer[i * 2];
                    out2Buf[i] += buf->buffer[i * 2 + 1];
                }
            }
        }
        cerr << "\r" << flush;
    }

    if (end) {
        // Draw the meter.

        // Quantize the position to multiples of the end.
        int tempEnd = end;
        if (pos > end)
            tempEnd = (pos / end + 1) * end;

        cerr << "\n[\033[44m";
        // We're using 40 as a meter width, should use the terminal width.
        int width = (40 * pos) / tempEnd;
        for (int i = 0; i < width; ++i)
            cerr << ' ';
        cerr << "\033[0m";
        for (int i = 0; i < 40 - width; ++i)
            cerr << ' ';
        cerr << "]\033[K\r\033[1A" << flush;
    }

    if (playing || recordChannel != -1) {
        if (recordChannel == -1 || impl->recordMode == JackEngineImpl::wrap)
            // Wrap on the end if we're either not recording or we're
            // recording in wrap mode.
            impl->pos.store(end ? (pos + nframes) % end :
                                  (pos + nframes),
                            memory_order_relaxed
                            );
        else
            // Recording in expand mode, just keep growing.
            impl->pos.store(pos + nframes, memory_order_relaxed);
    }
}

void JackEngine::startRecord(int channel) {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    impl->recordChannel.store(channel, memory_order_relaxed);
}

void JackEngine::endRecord() {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    impl->recordChannel.store(-1, memory_order_relaxed);
}

int JackEngine::getRecordChannel() const {
    const JackEngineImpl *impl = static_cast<const JackEngineImpl *>(this);
    return impl->recordChannel.load(memory_order_relaxed);
}

void JackEngine::startPlay() {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    impl->playing.store(1, memory_order_relaxed);
}

void JackEngine::endPlay() {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    impl->playing.store(0, memory_order_relaxed);
}

bool JackEngine::isPlaying() const {
    const JackEngineImpl *impl = static_cast<const JackEngineImpl *>(this);
    return impl->playing.load(memory_order_relaxed);
}

void JackEngine::clear() {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    impl->command.store(clearCmd, memory_order_relaxed);
}
