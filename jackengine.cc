#include "jackengine.h"

#include <jack/jack.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <atomic_ops.h>

#include <iostream>
#include <vector>

using namespace std;

static int jack_callback(jack_nframes_t nframes, void *arg) {
    reinterpret_cast<JackEngine*>(arg)->process(nframes);
    return 0;
}

namespace {

struct WaveBuf {
    size_t size;
    float *buffer;
    WaveBuf *next;

    WaveBuf(size_t size) :
        size(size),
        buffer(new float[size]),
        next(this) {
    }
};

struct Channel {
    WaveBuf *buf;

    // "enabled" means that a channel is playing audio.
    bool enabled;

    // Create a channel and allocate an initial buffer.
    Channel(int nframes) : buf(new WaveBuf(nframes)), enabled(true) {}

    WaveBuf *addBuf(int nframes) {
        WaveBuf *newBuf = new WaveBuf(nframes);
        newBuf->next = buf->next;
        buf->next = newBuf;
        buf = newBuf;
        return newBuf;
    }

    WaveBuf *nextBuf() {
        buf = buf->next;
        return buf;
    }
};

class JackEngineImpl : public JackEngine {
    public:

        jack_client_t *client;
        jack_port_t *in1, *in2, *out1, *out2;
        size_t arenaSize;
        std::vector<Channel> channels;
        size_t recordChannel, playing;

        JackEngineImpl(const char *name) :
                client(0),
                recordChannel(-1),
                playing(0) {
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
    int recordChannel = AO_load(&impl->recordChannel);
    if (recordChannel != -1) {
        // Allocate a new buffer for the channel if necessary.
        Channel *channel;
        WaveBuf *buf;
        if (recordChannel >= impl->channels.size()) {
            impl->channels.push_back(Channel(nframes * 2));
            channel = &impl->channels.back();
            buf = channel->buf;
        } else {
            channel = &impl->channels[recordChannel];
            buf = channel->addBuf(nframes * 2);
        }

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
    }

    if (AO_load(&impl->playing)) {
        int channelIndex = 0;
        for (Channel &channel : impl->channels) {
            if (channel.enabled && recordChannel != channelIndex) {
                WaveBuf *buf = channel.nextBuf();
                for (int i = 0; i < nframes; ++i) {
                    out2Buf[i] += buf->buffer[i * 2];
                    out2Buf[i] += buf->buffer[i * 2 + 1];
                }
            }
            ++channelIndex;
        }
    }
}

void JackEngine::startRecord(int channel) {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    AO_store(&impl->recordChannel, channel);
}

void JackEngine::endRecord() {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    AO_store(&impl->recordChannel, -1);
}

void JackEngine::startPlay() {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    AO_store(&impl->playing, 1);
}

void JackEngine::endPlay() {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    AO_store(&impl->playing, 0);
}

int main(int argc, const char **argv) {
    JackEngine *engine = JackEngine::create("foobar");
    engine->startPlay();
    bool recording = false;
    int channel = 0;
    while (true) {
        char *line = 0;
        size_t size;
        getline(&line, &size, stdin);
        recording = !recording;
        if (recording)
            engine->startRecord(channel++);
        else
            engine->endRecord();
        free(line);
    }
}
