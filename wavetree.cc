#include "wavetree.h"

#include <assert.h>

#include <iostream>

using namespace std;

class WaveTreeNode {
    protected:
        // The position of the wave node relative to the parent measured in
        // samples.
        int pos;

        // The number of samples covered by the node.
        int size;

        WaveTreeNode(int pos, int size) : pos(pos), size(size) {}

    public:

        virtual ~WaveTreeNode() {}

        // Returns the wave buffer at the given position or null if that
        // position is empty, unless "create" is true, in which case a new
        // buffer will be created at the position if none exists.
        virtual WaveBuf *get(int pos, bool create = false) = 0;


        // Make a new root node.  This should be called only on an existing
        // root node.  It converts the position of the receiver to be
        // relative to the new parent.
        WaveTreeNode *makeNewRoot();

        int getPos() const { return pos; }
        int getSize() const { return size; }
};

namespace {

const int slotsPerNode = 10;

// Number of frames in an input buffer.  Should be set by
int framesPerBuffer = 1024;

class WaveTreeLeaf : public WaveTreeNode {
    private:
        WaveBuf *buf;

    public:
        WaveTreeLeaf(int pos, int size) :
            WaveTreeNode(pos, size),
            buf(new WaveBuf(size * 2)) {
        }

        virtual ~WaveTreeLeaf() {
            delete buf;
        }

        virtual WaveBuf *get(int pos, bool create) {
            if (pos != this->pos) {
                cerr << "leaf reference is not the leaf pos.  Leaf pos = " <<
                    this->pos << " reference is " << pos << endl;
                return 0;
            }

            return buf;
        }
};

class WaveTreeInner : public WaveTreeNode {
    public:
        // We're making children "public" so it can be assigned from
        // WaveTreeNode.
        WaveTreeNode *children[slotsPerNode];

        WaveTreeInner(int pos, int size) : WaveTreeNode(pos, size) {
            for (WaveTreeNode *&child : children)
                child = 0;
        }

        ~WaveTreeInner() {
            for (WaveTreeNode *child : children)
                delete child;
        }

        virtual WaveBuf *get(int pos, bool create) {
            int index = (pos - this->pos) / (size / slotsPerNode);

            if (index < 0 || index > slotsPerNode) {
                cerr << "slot reference out of range: " << index << endl;
                return 0;
            }

            WaveTreeNode *child = children[index];
            if (!child) {
                int childSize = size / 10;
                if (create) {
                    // Allocate either an inner node or a leaf depending on
                    // size/10 is the size of a single buffer.
                    int childPos = index * childSize;
                    children[index] = child =
                        (childSize == framesPerBuffer) ?
                            static_cast<WaveTreeNode *>(
                                new WaveTreeLeaf(childPos, childSize)
                            ) :
                            static_cast<WaveTreeNode *>(
                                new WaveTreeInner(index * childSize, childSize)
                            );
                } else {
                    return 0;
                }
            }

            return child->get(pos - this->pos, create);
        }
};

} // anonymous namespace

WaveTreeNode *WaveTreeNode::makeNewRoot()  {
    // create a new inner node.
    int parentSize = size * 10;
    int newRelPos = pos % parentSize;
    int newRootPos = pos - newRelPos;
    assert(newRootPos >= 0);

    // Create a new root node with an absolute position.  Add this
    // node as its child.
    WaveTreeInner *newRoot =
        new WaveTreeInner(newRootPos, parentSize);
    newRoot->children[newRelPos / size] = this;

    // Convert the position to relative to the new parent.
    pos = newRelPos;

    return newRoot;
}

WaveBuf *WaveTree::get(int pos, bool create) {
    if (!root) {
        if (create)
            root = new WaveTreeLeaf(pos, framesPerBuffer);
        else
            return 0;
    } else {
        int rootPos = root->getPos();

        // If the position is out of range, continue to create intermediate
        // nodes until we have one big enough to hold both the new child and
        // the existing one.
        while (pos < rootPos || pos >= rootPos + root->getSize()) {
            root = root->makeNewRoot();
            rootPos = root->getPos();
        }
    }

    return root->get(pos, create);
}

WaveTree::~WaveTree() {
    delete root;
}

void WaveTree::setBufferSize(int nframes) {
    framesPerBuffer = nframes;
}

int WaveTree::getBufferSize() {
    return framesPerBuffer;
}
