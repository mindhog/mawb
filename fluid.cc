
#include "fluid.h"

#include <fluidsynth.h>
#include <iostream>

using namespace awb;
using namespace std;

FluidSynthDispatcher::FluidSynthDispatcher() {
    settings = new_fluid_settings();
    synth = new_fluid_synth(settings);
    driver = new_fluid_audio_driver(settings, synth);
}

FluidSynthDispatcher::~FluidSynthDispatcher() {
    delete_fluid_synth(synth);
    delete_fluid_settings(settings);
}

void FluidSynthDispatcher::loadFont(const char *filename, bool resetPresets) {
    fluid_synth_sfload(synth, filename, resetPresets);
}

void FluidSynthDispatcher::onEvent(Event *event) {
    switch (event->getType()) {
        case Event::NOTE_ON: {
            NoteOn *note = static_cast<NoteOn *>(event);
            fluid_synth_noteon(synth, note->channel, note->note,
                               note->velocity
                               );
            break;
        }
        case Event::NOTE_OFF: {
            NoteOff *note = static_cast<NoteOff *>(event);
            fluid_synth_noteoff(synth, note->channel, note->note);
            break;
        }
        default:
            cerr << "Event " << *event <<
                " not implemented in FluidSynthDispatcher" << endl;
    }
}

