#include "term.h"

#include <termios.h>
#include <unistd.h>

#include <iostream>

#include "jackengine.h"

using namespace awb;
using namespace std;

Term::Term(JackEngine &jackEngine) : jackEngine(jackEngine) {
    // Switch to "raw" mode.
    struct termios mode;
    tcgetattr(/*file_descriptor*/ 0, &mode);
    mode.c_iflag = 0;
    mode.c_oflag &= ~OPOST;
    mode.c_lflag &= ~(ISIG | ICANON | ECHO);
    tcsetattr(/*file_descriptor*/ 0, TCSADRAIN, &mode);
}

Term::~Term() {
    // Restore cooked mode.
    struct termios mode;
    tcgetattr(/*file_descriptor*/ 0, &mode);
    mode.c_iflag = BRKINT | IGNPAR | ISTRIP | ICRNL | IXON;;
    mode.c_oflag |= OPOST;
    mode.c_lflag |= ISIG | ICANON | ECHO;
    tcsetattr(/*file_descriptor*/ 0, TCSADRAIN, &mode);
}

void Term::handleRead(spug::Reactor &reactor) {
    char buffer[1024];
    int amtRead = read(0, buffer, sizeof(buffer));

    for (int i = 0; i < amtRead; ++i) {
        char ch = buffer[i];
        if (ch >= '0' && ch <= '9') {
            int curRecordChannel = jackEngine.getRecordChannel();
            if (curRecordChannel == -1) {
                jackEngine.startRecord(ch - '0');
                cerr << "Recording on channel " <<
                    jackEngine.getRecordChannel() << "\r" << endl;
            } else {
                cerr << "Finished recording on channel " << curRecordChannel <<
                    "\r" << endl;
                jackEngine.endRecord();
            }
        } else if (ch == ' ') {
            if (jackEngine.isPlaying())
                jackEngine.endPlay();
            else
                jackEngine.startPlay();
        } else if (ch == 'K') {
            jackEngine.clear();
            cerr << "\033[31;43mDeleted\033[0m\r" << endl;
        } else if (ch == 'q') {
            throw Quit();
        }
    }
}

bool Term::isTTY() {
    return isatty(0);
}
