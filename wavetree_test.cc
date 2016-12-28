
#include "wavetree.h"

#include <assert.h>

#include <iostream>

using namespace std;

int main() {
    if (true) {
        WaveTree tree;

        assert(tree.get(4096) == 0);

        WaveBuf *buf = tree.get(4096, true);
        assert(buf);
        buf->buffer[0] = 1234.0;
        buf->buffer[1] = 4567.0;

        assert(tree.get(4096, false) == buf);

        // Now try adding something at zero.
        buf = tree.get(0, true);
        assert(buf);
        assert(tree.get(0) == buf);

        // Now try adding something beyond the index.
        buf = tree.get(16384, true);
        assert(buf);
        assert(tree.get(16384) == buf);

        // XXX need to make sure we've preserved the old buffers.
    }

    cout << "ok" << endl;
}
