#ifndef awb_wavetree_h_
#define awb_wavetree_h_

#include <unistd.h>

class WaveTreeNode;

struct WaveBuf {
    size_t size;
    float *buffer;

    WaveBuf(size_t size) :
        size(size),
        buffer(new float[size]) {
    }

    ~WaveBuf() { delete buffer; }
};


// WaveTree is a sparse tree of WaveBuf's.
// Every buffer must be of the same size WaveTree::framesPerBuffer.
class WaveTree {
    private:
        WaveTreeNode *root;

    public:
        WaveTree() : root(0) {}
        virtual ~WaveTree();
        virtual WaveBuf *get(int pos, bool create = false);\

        // Set the number of samples in a buffer.
        static void setBufferSize(int nframes);

        static int getBufferSize();
};

#endif
