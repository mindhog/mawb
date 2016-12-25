#ifndef awb_jackengine_h_
#define awb_jackengine_h_

class JackEngine {
    public:
        static JackEngine *create(const char *name);

        // Process some number of frames.
        void process(unsigned int nframes);

        void startRecord(int channel);
        void endRecord();

        void startPlay();
        void endPlay();
};

#endif
