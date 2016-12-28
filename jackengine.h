#ifndef awb_jackengine_h_
#define awb_jackengine_h_

namespace awb {

class JackEngine {
    public:
        static JackEngine *create(const char *name);

        // Process some number of frames.
        void process(unsigned int nframes);

        void startRecord(int channel);
        void endRecord();

        // Returns the channel that is currently being recorded, -1 if not
        // recording.
        int getRecordChannel() const;

        void startPlay();
        void endPlay();
        bool isPlaying() const;
};

} // namespace awb

#endif
