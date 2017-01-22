#include "jackengine.h"

#include <assert.h>
#include <jack/jack.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>

#include <atomic>
#include <iostream>
#include <sstream>
#include <vector>

#include <spug/RCBase.h>
#include <spug/RCPtr.h>

#include "mawb.pb.h"
#include "wavetree.h"

using namespace awb;
using namespace mawb;
using namespace spug;
using namespace std;

static int jack_callback(jack_nframes_t nframes, void *arg) {
    reinterpret_cast<JackEngine*>(arg)->process(nframes);
    return 0;
}

namespace {

SPUG_RCPTR(Channel);

struct Channel : public RCBase {
    WaveTree *data;

    // "enabled" means that a channel is playing audio.
    bool enabled;

    // The end position of the loop stored in the channel.
    int end;

    // If non-zero, this is the "loop position" in span relative mode.  During
    // lookup, values before the loop position are offset by 'end', having the
    // effect of wraping around in the channel's span.
    int loopPos;

    // The position at the time we began recording the current channel (this
    // is only meaningful when the channel is being recorded)
    int startPos;

    // The position when we started recording 'data'.  This is added to the
    // position when we look up buffers from audio data during replay.
    int offset;

    // Create a channel and allocate an initial buffer.
    Channel() :
        data(new WaveTree()),
        enabled(true),
        loopPos(0),
        startPos(0),
        offset(0) {
    }

    ~Channel() {
        delete data;
    }

    Channel(const Channel &other) = delete;

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

        // wrap to the end if necessary.
        if (pos < loopPos)
            pos += end;

        cerr << " (" << pos << ") " << flush;

        return data->get(pos * 2, false);
    }

    void storeIn(Wave &wave) const {
        wave.set_enabled(enabled);
        wave.set_end(end);
        wave.set_looppos(loopPos);
        wave.set_offset(offset);

        // Store the wave data.
        int bufSize = WaveTree::getBufferSize() / 2;
        ostringstream temp;
        for (int i = offset; i < end + offset; i += bufSize) {
            WaveBuf *buf = data->get(i * 2);
            if (buf) {
                for (int j = 0; j < bufSize * 2; ++j) {
                    int val = buf->buffer[j] * 32768;
                    temp << static_cast<char>(val >> 8);
                    temp << static_cast<char>(val & 0xFF);
                }
            } else {
                for (int j = 0; j < bufSize * 2; ++j) {
                    temp << "\0\0";
                }
            }
        }
        wave.set_data(temp.str());
    }

    void loadFrom(const Wave &wave) {
        enabled = wave.enabled();
        end = wave.has_end() ? wave.end() : 0;
        loopPos = wave.has_looppos() ? wave.looppos() : 0;
        offset = wave.has_offset() ? wave.offset() : 0;

        // Retrieve wave data.
        const string &temp = wave.data();
        int bufSize = WaveTree::getBufferSize() / 2;
        for (int i = offset; i < end + offset; i += bufSize) {
            WaveBuf *buf = data->get(i * 2, true);
            for (int j = 0; j < bufSize * 2; ++j) {
                int index = (i - offset) * 4 + j * 2;
                if (index < temp.size()) {
                    buf->buffer[j] = static_cast<float>(
                        ((temp[index] << 8) |
                        (temp[index + 1] & 0xFF)) /
                        32768.0
                    );
                }
            }
        }
    }
};

SPUG_RCPTR(SectionObj);

class SectionObj : public RCBase {
    public:
        vector<ChannelPtr> channels;

        // End of the section span.
        int end;

        SectionObj() : end(0) {}
};

enum Command {
    // Don't do anything.  We start with this and reserve the zero value so
    // that we also use the command enum as a boolean.
    noopCmd = 0,

    // clear all channels, reset to a pristine state.
    clearCmd,

    // Begin a new section as soon as we end the current section or begin
    // recording.
    newSectionCmd,

    // Begin the next or previous section (same cases as newSectionCmd).
    nextSectionCmd,
    prevSectionCmd,
};

class JackEngineImpl : public JackEngine {
    public:

        jack_client_t *client;
        jack_port_t *in1, *in2, *out1, *out2;
        SectionObjPtr section;
        atomic_int recordChannel, playing;
        atomic_int pos;

        // The list of sections and an ordinal indicating which section is
        // current.
        vector<SectionObjPtr> sections;
        int sectionIndex;

        // Commands sent from other threads.
        atomic<Command> command;

        // The record mode.
        atomic<RecordMode> recordMode;

        // Set to true when we process a buffer while recording.  This lets us
        // keep track of the state changes as we go from recording to not.
        bool recording;

        // The last channel we were recording on.
        int lastRecordChannel;

        // When one of the section change commands has been sent, this is set
        // to that command.  It causes the engine to continue playing the
        // current section until either we reach the end of it or recording
        // has been initiated for one of the channels.
        Command newSectionLatched;

        // True if the engine has been initialized.
        bool initialized;

        // The denominator of the fraction of a second of error margin used in
        // determining loop alignment.  For example, 4 would be a quarter
        // second.
        int errorMargin = 4;

        JackEngineImpl(const char *name) :
                client(0),
                section(new SectionObj()),
                recordChannel(-1),
                playing(0),
                pos(0),
                sectionIndex(0),
                command(noopCmd),
                recordMode(spanRelative),
                recording(false),
                lastRecordChannel(-1),
                newSectionLatched(noopCmd),
                initialized(false) {
            sections.push_back(section);
            sectionIndex = 0;

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

        void store(ostream &out) const {
            ProjectFile pf;
            pf.set_sectionindex(sectionIndex);

            for (const auto sec : sections) {
                Section *secData = pf.add_section();
                secData->set_end(sec->end);
                for (const auto channel : section->channels) {
                    cerr << "\033[36msaving channel\r" << endl;
                    Wave *wave = secData->add_waves();
                    channel->storeIn(*wave);
                }
            }

            pf.SerializeToOstream(&out);
            cerr << "\033[32mWrote to outfile.\r" << endl;
        }

        void load(istream &in) {
            sections.clear();
            ProjectFile pf;
            pf.ParseFromIstream(&in);
            sectionIndex = pf.sectionindex();

            for (int i = 0; i < pf.section_size(); ++i) {
                const Section &sec = pf.section(0);
                section = new SectionObj();
                section->end = sec.end();
                sections.push_back(section);

                for (const auto &wave : sec.waves()) {
                    ChannelPtr channel = new Channel();
                    section->channels.push_back(channel);
                    channel->loadFrom(wave);
                }
            }
        }

        SectionObjPtr changeSections() {
            cerr << "\r\n\033[33mChanging to ";
            switch (newSectionLatched) {
                case newSectionCmd:
                    cerr << "new section\r" << endl;
                    section = new SectionObj();
                    sections.push_back(section);
                    sectionIndex = sections.size() - 1;
                    break;

                case nextSectionCmd:
                    cerr << "next section\r" << endl;
                    sectionIndex = (sectionIndex + 1) % sections.size();
                    section = sections[sectionIndex];
                    break;

                case prevSectionCmd:
                    cerr << "prev section\r" << endl;
                    sectionIndex = (sectionIndex - 1) % sections.size();
                    section = sections[sectionIndex];
                    break;

                default:
                    assert(false && "Invalid section type");
            }

            newSectionLatched = noopCmd;
            return section;
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
    int &end = impl->section->end;

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
            impl->section = new SectionObj();
            impl->command.store(noopCmd, memory_order_relaxed);
            impl->playing.store(true, memory_order_relaxed);
            break;
        case noopCmd:
            break;
        case newSectionCmd:
            cerr << "\r\nlatched for new section\r" << endl;
            impl->newSectionLatched = newSectionCmd;
            impl->command.store(noopCmd, memory_order_relaxed);
            break;
        case nextSectionCmd:
            cerr << "\r\nlatched for next section\r" << endl;
            impl->newSectionLatched = nextSectionCmd;
            impl->command.store(noopCmd, memory_order_relaxed);
            break;
        case prevSectionCmd:
            cerr << "\r\nlatched for prev section\r" << endl;
            impl->newSectionLatched = prevSectionCmd;
            impl->command.store(noopCmd, memory_order_relaxed);
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
    SectionObjPtr section = impl->section;
    if (recordChannel != -1) {
        // Recording.
        // If we weren't previously recording, initiate recording state.
        bool startedRecording = false;
        if (!impl->recording) {
            // Start a new section if we're latched.
            if (impl->newSectionLatched)
                section = impl->changeSections();

            if (impl->section->channels.empty())
                pos = 0;
            impl->recording = true;
            impl->lastRecordChannel = recordChannel;
            startedRecording = true;
        }

        // Allocate a new channel if necessary.
        ChannelPtr channel;
        if (recordChannel >= section->channels.size()) {
            section->channels.push_back(channel = new Channel());
            if (recordChannel != section->channels.size() - 1) {
                recordChannel = section->channels.size() - 1;
                impl->recordChannel.store(recordChannel, memory_order_relaxed);
                impl->lastRecordChannel = recordChannel;
            }
        } else {
            channel = section->channels[recordChannel];
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

            ChannelPtr channel = section->channels[impl->lastRecordChannel];

            // Store the end of the record channel.
            if (impl->recordMode == JackEngineImpl::expand && end) {

                // If we started recording very shortly before the end of the
                // span, we assume that we want to line up with the start of
                // the span so set the offset accordingly.
                cerr << "frame begins at " <<
                    ((end - channel->startPos) * 100 / end) <<
                    " percent (" <<
                    (float(end - channel->startPos) / framesPerSecond) <<
                    "/" << (float(end) / framesPerSecond) <<
                    " seconds) before end of span\r" << endl;
                if (end - channel->startPos < framesPerSecond / 10)
                    channel->offset = end;
                else
                    channel->offset = 0;

                // If we exceeded the end by more than a tenth of a second
                // (human error) in expand mode, we want to adjust the end to
                // be the first multiple of end that is greater than the
                // current pos.
                if (pos - channel->offset > end +
                    framesPerSecond / impl->errorMargin) {
                    int localPos = pos - channel->offset;
                    int multiple = localPos / end;

                    // We normally want to increment the multiple because,
                    // for example, for a new span that is 1.5 times the
                    // length of the old span we'd get a multiple of 1 and
                    // we'd want a multiple of 2. But only do this if we
                    // exceeed the last boundary by the "jitter delay" (so,
                    // for example, 1.1 seconds would still count as just 1).
                    if (localPos - end * multiple >
                         framesPerSecond / impl->errorMargin)
                        ++multiple;
                    localPos = end * multiple;

                    end = localPos;
                    cerr << "changed end to " << end << " (multiple of " <<
                        multiple << ")\r" << endl;
                }
            } else if (impl->recordMode == JackEngineImpl::spanRelative && end) {

                cerr << "\r\nend is " << end << ", ";

                // Get the position relative to the start position and trim
                // anything that looks like human error.
                int relPos = pos - channel->startPos;
                if (relPos % end < framesPerSecond / impl->errorMargin) {
                    relPos = (relPos / end) * end;

                    // Deal with the pathological case where the entire riff
                    // is less than the margin for error.
                    if (!relPos) {
                        cerr << "expanding really short riff!\r\n" << endl;
                        relPos = end;
                    }
                }

                // If the new span exceeds the old span, adjust the ending to
                // be at the beginning of the last frame.
                if (relPos > end) {
                    // Quantize around the size of the span.
                    end = (relPos / end + (relPos % end ? 1 : 0)) * end;
                    channel->loopPos = channel->startPos;
                    cerr << "expanding. ";
                } else if (channel->startPos < end && pos < end) {
                    // The new recording is entirely within the current span,
                    // so this is just like wrap mode.
                    channel->loopPos = 0;
                    cerr << "wrapping. ";
                } else {
                    // The new recording must overlap the end.  Make the loop
                    // pos the start pos.
                    channel->loopPos = channel->startPos;
                    cerr << "offset loop. ";
                }

                cerr << "loop pos = " << channel->loopPos << " new end = " <<
                    end << " recording size = " << relPos <<
                    "\r\n" << flush;
            }

            // if we finished recording the first channel, store the end.
            if (!end) {
                end = pos;
                impl->pos.store(0, memory_order_relaxed);
            }

            if (!channel->end)
                channel->end = end;
            cerr << "recorded channel {offset: " << channel->offset <<
                ", end = " << channel->end << "} engine end = " << end <<
                "\r" << endl;
        }
    }

    // Playback.
    bool playing = impl->playing.load(memory_order_relaxed);
    if (playing) {
        int channelIndex = -1;
        for (auto channel : section->channels) {
            ++channelIndex;
            if (channel->enabled && recordChannel != channelIndex) {
                assert(channel->end);
                cerr << channelIndex << ": ";
                WaveBuf *buf = channel->getReadBuffer(pos);
                if (!buf) continue;

                for (int i = 0; i < nframes; ++i) {
                    out1Buf[i] += buf->buffer[i * 2];
                    out2Buf[i] += buf->buffer[i * 2 + 1];
                }
            }
        }
        cerr << "\r" << flush;
    }

    if (end && playing) {
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
        cerr << "]\033[K";

        cerr << " " << pos << "/" << end;

        cerr << "\r\033[1A" << flush; // BOL and hide the cursor.
    }

    if (playing || recordChannel != -1) {
        if (recordChannel == -1 || impl->recordMode == JackEngineImpl::wrap) {
            // Wrap on the end if we're either not recording or we're
            // recording in wrap mode.
            impl->pos.store(end ? (pos + nframes) % end :
                                  (pos + nframes),
                            memory_order_relaxed
                            );

            // If we're latched to begin a new section and we're at the end
            // of the current section, do the section switch now.
            if (impl->newSectionLatched && pos + nframes >= end)
                impl->changeSections();
        } else {
            // Recording in one of the expand modes, just keep growing.
            impl->pos.store(pos + nframes, memory_order_relaxed);
        }
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

void JackEngine::startNewSection() {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    impl->command.store(newSectionCmd, memory_order_relaxed);
}

void JackEngine::startNextSection() {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    impl->command.store(nextSectionCmd, memory_order_relaxed);
}

void JackEngine::startPrevSection() {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    impl->command.store(prevSectionCmd, memory_order_relaxed);
}

void JackEngine::store(ostream &out) {
    const JackEngineImpl *impl = static_cast<const JackEngineImpl *>(this);
    if (isPlaying() || impl->recordChannel.load(memory_order_relaxed) != -1) {
        cerr << "\033[31mCan't save/load while playing or recording (hit "
                "pause)\r" << endl;
        return;
    }
    impl->store(out);
}

void JackEngine::load(istream &in) {
    JackEngineImpl *impl = static_cast<JackEngineImpl *>(this);
    if (isPlaying() || impl->recordChannel.load(memory_order_relaxed) != -1) {
        cerr << "\033[31mCan't save/load while playing or recording (hit "
                "pause)\r" << endl;
        return;
    }
    impl->load(in);
}
