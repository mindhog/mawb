#include "serial.h"

#include <iostream>
#include <unistd.h>

#include "jackengine.h"

using namespace awb;
using namespace std;

void Serial::handleRead(spug::Reactor &reactor) {
    char buffer[1024];
    int amtRead = read(fd, buffer, sizeof(buffer));

    for (int i = 0; i < amtRead; ++i) {
        char ch = buffer[i];
        cerr << "serial: " << int(ch) << "\r" << endl;

        if (ch & 0x80)
            jackEngine.endRecord();
        else
            jackEngine.startRecord(ch);
    }
}
