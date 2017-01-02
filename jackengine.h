#ifndef awb_jackengine_h_
#define awb_jackengine_h_

namespace awb {

class JackEngine {
    public:

        enum RecordMode {

            // When recording past the end of the current measure, wrap around
            // to the beginning of the buffer.
            wrap,

            // If we record past the end, continue recording and quantize to
            // the span to the new position.
            expand,
        };


        static JackEngine *create(const char *name);

        // Process some number of frames.
        void process(unsigned int nframes);

        void startRecord(int channel);
        void endRecord();
        void setRecordMode(RecordMode mode);

        // Returns the channel that is currently being recorded, -1 if not
        // recording.
        int getRecordChannel() const;

        void startPlay();
        void endPlay();
        bool isPlaying() const;

        // Clear all buffers, restore the engine to a pristine state.
        void clear();
};

} // namespace awb

#endif
