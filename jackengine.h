#ifndef awb_jackengine_h_
#define awb_jackengine_h_

#include <iostream>

namespace awb {

class JackEngine {
    private:
        void closeRecordChannel(const int pos);

    public:

        enum RecordMode {

            // When recording past the end of the current span, wrap around
            // to the beginning of the buffer.
            wrap,

            // If we record past the end, continue recording and quantize to
            // the span to the new position.
            expand,

            // Allow recording past the end of the span, like in expand mode,
            // but also let the current record drive when it is looped so that
            // we can begin looping in the same span that we ended in.
            spanRelative,
        };

        ~JackEngine();

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

        // Set the "sticky" flag on the channel.  A sticky channel will
        // transfer its state to the corresponding channel in a new section.
        void setSticky(int channel, bool sticky);

        // Get the sticky flag for a channel.
        bool getSticky(int channel) const;

        // Clear all buffers, restore the engine to a pristine state.
        void clear();

        // Start a new section as soon as the old section ends or when record
        // is initiated.
        void startNewSection();

        // Start the previous section as soon as the old section ends or when
        // record is initiated.
        void startPrevSection();

        // Start the next section as soon as the old section ends or when
        // record is initiated.
        void startNextSection();

        void store(std::ostream &out);
        void load(std::istream &in);
};

} // namespace awb

#endif
