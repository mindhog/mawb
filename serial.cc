#include "serial.h"

#include <iostream>
#include <unistd.h>

#include "jackengine.h"

using namespace awb;
using namespace std;

static int sectionCount = 1;
static int sectionIndex = 0;

void Serial::handleRead(spug::Reactor &reactor) {
    char buffer[1024];
    int amtRead = read(fd, buffer, sizeof(buffer));

    for (int i = 0; i < amtRead; ++i) {
        char ch = buffer[i];
        cerr << "serial: " << int(ch) << "\r" << endl;

        if (ch == 9) {
            if (sectionIndex + 1 == sectionCount) {
                jackEngine.startNewSection();
                sectionIndex++;
                sectionCount++;
            } else {
                jackEngine.startNextSection();
                sectionIndex++;
            }
            continue;
        } else if (ch == 8) {
            jackEngine.startPrevSection();
            sectionIndex = (sectionIndex - 1) % sectionCount;
            continue;
        }

        if (ch & 0x80)
            jackEngine.endRecord();
        else
            jackEngine.startRecord(ch);
    }
}
