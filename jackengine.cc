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

    // Create a channel and allocate an initial buffer.
    Channel() : data(new WaveTree()), enabled(true) {}
};

class JackEngineImpl : public JackEngine {
    public:

        jack_client_t *client;
        jack_port_t *in1, *in2, *out1, *out2;
        size_t arenaSize;
        vector<Channel> channels;
        atomic_int recordChannel, playing;
        atomic_int pos;

        // The end sample position.  At this point, we start looping.
        int end;

        // Set to true when we process a buffer while recording.  This lets us
        // keep track of the state changes as we go from recording to not.
        bool recording;

        // True if the engine has been initialized.
        bool initialized;

        JackEngineImpl(const char *name) :
                client(0),
                recordChannel(-1),
                playing(0),
                pos(0),
                end(0),
                recording(false),
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

} // anon namespace

JackEngine *JackEngine::create(const char *name) {
    return new JackEngineImpl(name);
}

void JackEngine::process(unsigned int nframes) {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);

    // Initialize if necessary.
    if (!impl->initialized) {
        WaveTree::setBufferSize(nframes * 2);
        impl->initialized = true;
    } else {
        assert(nframes * 2 == WaveTree::getBufferSize());
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
        if (!impl->recording) {
            if (impl->channels.empty())
                pos = 0;
            impl->recording = true;
        }

        // Allocate a new channel if necessary.
        Channel *channel;
        if (recordChannel >= impl->channels.size()) {
            impl->channels.push_back(Channel());
            channel = &impl->channels.back();
        } else {
            channel = &impl->channels[recordChannel];
        }

        WaveBuf *buf = channel->data->get(pos * 2, true);
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

        // If we were recording but are no longer, flip the flag.
        if (impl->recording)
            impl->recording = false;

        // if we finished recording the first channel, store the end.
        if (!impl->end && !impl->channels.empty()) {
            impl->end = pos;
            impl->pos.store(0, memory_order_relaxed);
        }
    }

    bool playing = impl->playing.load(memory_order_relaxed);
    if (playing) {
        int channelIndex = 0;
        for (Channel &channel : impl->channels) {
            if (channel.enabled && recordChannel != channelIndex) {
                WaveBuf *buf = channel.data->get(pos * 2);
                if (!buf) continue;

                for (int i = 0; i < nframes; ++i) {
                    out2Buf[i] += buf->buffer[i * 2];
                    out2Buf[i] += buf->buffer[i * 2 + 1];
                }
            }
            ++channelIndex;
        }
    }

    if (playing || recordChannel != -1) {
        impl->pos.store(impl->end ? (pos + nframes) % impl->end :
                                    (pos + nframes),
                        memory_order_relaxed
                        );
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
