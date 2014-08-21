
#ifndef awb_fluid_h_
#define awb_fluid_h_

#include "event.h"
#include "engine.h"

typedef struct _fluid_hashtable_t fluid_settings_t;
typedef struct _fluid_synth_t fluid_synth_t;
typedef struct _fluid_audio_driver_t fluid_audio_driver_t;

namespace awb {

SPUG_RCPTR(FluidSynthDispatcher);

class FluidSynthDispatcher : public EventDispatcher {
    private:
        fluid_settings_t *settings;
        fluid_synth_t *synth;
        fluid_audio_driver_t *driver;

    public:
        FluidSynthDispatcher();
        ~FluidSynthDispatcher();

        // Load a sound-font.
        void loadFont(const char *filename, bool resetPresets);

        virtual void onEvent(Event *event);
        virtual void onIdle();
};


} // namespace awb

#endif
