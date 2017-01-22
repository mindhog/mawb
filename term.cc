#include "term.h"

#include <termios.h>
#include <unistd.h>

#include <iostream>
#include <fstream>

#include "jackengine.h"

using namespace awb;
using namespace std;

Term::Term(JackEngine &jackEngine) : jackEngine(jackEngine), mode(KEY_CMD) {
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
        if (mode == KEY_CMD) {
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
                cerr << "\033[31;43mDeleted\033[0m\r\n\033[K" << flush;
            } else if (ch == 'q') {
                throw Quit();
            } else if (ch == 's') {
                if (jackEngine.isPlaying())
                    jackEngine.endPlay();
                cerr << "\nsave file: " << flush;
                lastCmd = CMD_STORE;
                mode = LINE_READ;
            } else if (ch == 'l') {
                if (jackEngine.isPlaying())
                    jackEngine.endPlay();
                cerr << "\nload file: " << flush;
                lastCmd = CMD_LOAD;
                mode = LINE_READ;
            } else if (ch == ',') {
                jackEngine.startPrevSection();
            } else if (ch == '.') {
                jackEngine.startNextSection();
            } else if (ch == 'n') {
                jackEngine.startNewSection();
            }
        } else {
            // backspace.
            if (ch == 7 || ch == 127) {
                if (lineBuf.size()) {
                    cerr << "\b \b" << flush;
                    lineBuf = lineBuf.substr(0, lineBuf.size() - 1);
                }
            } else if (ch == '\r') {
                switch (lastCmd) {
                    // Processs whatever command we have waiting.
                    case CMD_LOAD: {
                        ifstream src(lineBuf);
                        jackEngine.load(src);
                        cerr << "\r\nloaded file " << lineBuf << "\r" << endl;
                        lineBuf = "";
                        break;
                    }
                    case CMD_STORE: {
                        ofstream dst(lineBuf);
                        jackEngine.store(dst);
                        cerr << "\r\nsaved file " << lineBuf << "\r" << endl;
                        lineBuf = "";
                        break;
                    }
                    default:
                        cerr << "Internal error: Unkwnown command.\r" << endl;
                }
                mode = KEY_CMD;
            } else {
                lineBuf = lineBuf + ch;
                cerr << ch << flush;
            }
        }

    }
}

bool Term::isTTY() {
    return isatty(0);
}
