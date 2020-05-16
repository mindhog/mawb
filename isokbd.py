#!/usr/bin/env python3
#==============================================================================
#
# Copyright 2020 Michael A. Muller
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#==============================================================================

"""Isomorphic keyboard controller.

This maps keyboard keys to midi in ways corresponding to several isomorphic
keyboard layouts.
"""

import sys
from amidi import getSequencer, PortInfo, Sequencer
from midi import Event as MidiEvent, NoteOn, NoteOff
from tkinter import BOTH, Event, EventType, Frame, Canvas, NSEW, Text, Tk, \
    Toplevel
from tkinter.font import Font
from typing import Callable, Dict, Optional, Union

# Note function: accepts an integer (the midi note value) and a bool (true is
# note on, false is note off)
NoteFunc = Callable[[int, bool], None]

rows = [
    'zxcvbnm,./',
    "asdfghjkl;\'",
    'qwertyuiop[]\\',
    '1234567890-='
]

def keychar(sym: str) -> str:
    """Returns a single character value for a keysym."""
    return {
        'backslash': '\\',
        'comma': ',',
        'period': '.',
        'slash': '/',
        'bracketleft': '[',
        'bracketright': ']',
        'semicolon': ';',
        'apostrophe': "'",
        'minus': '-',
        'equal': '=',
    }.get(sym, sym)

def makeWickiHayden() -> Dict[str, int]:
    """Returns a keyboard map modeled after Wicki-Haden keyboards."""
    keys = {}
    start = 30 # the "z" key, which we'll start at 30
    for row in rows:
        i = start
        for key in row:
            keys[key] = i
            i += 2

        # Next row starts at the 4th of the previous row (5 semitones)
        start += 5
    return keys

noteMap = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
def getNoteName(note: int) -> str:
    return noteMap[note % 12]

def makeJanko() -> Dict[str, int]:
    """Returns a keyboard map modeled after the Janko keyboard"""
    keys = {}
    start = 57
    for row in rows:
        i = start
        for key in row:
            keys[key] = i
            i += 2

        # row above is down a semitone
        start -= 1
    return keys

def makeHarmonic() -> Dict[str, int]:
    """Returns a keyboard map modeled after the Harmonic keyboard.

    Note that since on a harmonic keyobard, flat is "up", this shifts the
    orientation so that fifths are to the right and minor and major thirds are
    above.
    """
    keys = {}
    start = 42
    for row in rows:
        i = start
        for key in row:
            keys[key] = i
            i += 7

        # row above is down a semitone
        start -= 4
    return keys

def makeThirds() -> Dict[str, int]:
    """Returns a keyboard map modeled after a guitar-like instrument.

    Adjacent keys on the horizontal axis are a semi-tone apart and the key up
    and to the left is always a major third of the current key.
    """
    keys = {}
    start = 42
    for row in rows:
        i = start
        for key in row:
            keys[key] = i
            i += 1

        # row above is down a semitone
        start += 4
    return keys

def defaultNoteFunc(note: int, enabled: bool) -> None:
    print(f'note {note} {enabled and "on" or "off"}')

# Width factor: square root of three.  We use this to find the ratio from
# HEXHEIGHT to half the width of a hexagon.
WFACT = 1.73205

# 1/4 the height of a hexagon in pixels.  This is convenient because it can be
# used to compute the y coordinates of every point in the hexagon and also
# (via WFACT) the x coordinates.
HEXHEIGHT = 10

class IsoKbdWin(Frame):

    def __init__(self, keys: Dict[str, int],
                 playNote: NoteFunc = defaultNoteFunc,
                 toplevel: Union[Tk, Toplevel] = None
                 ):
        if toplevel is None:
            toplevel = Tk()

        self.__keys = keys

        super(IsoKbdWin, self).__init__(toplevel)

        self.__canvas = Canvas(self, background='#000011')
        self.__canvas.bind('<KeyPress>', self.on_key_event)
        self.__canvas.bind('<KeyRelease>', self.on_key_event)
        self.__canvas.pack(expand=True, fill = BOTH)
        self.__canvas.focus_set()
        self.__playNote = playNote
        self.pack(expand=True, fill = BOTH)

        self.textFont = Font(size=-HEXHEIGHT)
        self.draw_keyboard(HEXHEIGHT)

    def on_key_event(self, event: Event) -> Optional[str]:
        ch = keychar(event.keysym)
        poly_id = self.__key_polys.get(ch)
        note_num = self.__keys.get(ch)
        if poly_id is not None:
            if event.type == EventType.KeyPress:
                self.__canvas.itemconfig(poly_id, fill = '#0000ff')
                self.__playNote(note_num, True)
            else:
                self.__canvas.itemconfig(poly_id, fill = '#000000')
                self.__playNote(note_num, False)
            return 'break'
        else:
            print(event.keysym)
            return None

    def draw_keyboard(self, n: int) -> None:
        self.__key_polys : Dict[str, int] = {}
        y = n * 13 # 4 rows (3n each) plus padding.
        w = WFACT * n
        for i, row in enumerate(rows):
            x = int(w * (2 + 4 - i))
            for key in row:
                id = self.draw_hex(x, y, n)
                self.__key_polys[key] = id
                x += w * 2
            y -= 3 * n

        # Do the same with text so that all text ends up over all of the hexen.
        y = n * 13
        for i, row in enumerate(rows):
            x = int(w * (2 + 4 - i))
            for key in row:
                id = self.draw_text(x, y, n, key,
                                    getNoteName(self.__keys.get(key)))
                x += w * 2
            y -= 3 * n

    def draw_hex(self, x: int , y: int, n: int) -> int:
        w = WFACT * n
        return self.__canvas.create_polygon(
            x, y,
            x + w, y + n,
            x + w, y + n * 3,
            x, y + n * 4,
            x - w, y + n * 3,
            x - w, y + n,
            x, y,
            outline = '#ffffff')

    def draw_text(self, x: int, y: int, n: int, ch: str, note: str) -> int:
        self.__canvas.create_text(x, y + n, text=ch,
                                  fill='#ffff00',
                                  font=self.textFont)
        self.__canvas.create_text(x, y + n * 3, text=note,
                                  fill='#ffff00',
                                  font=self.textFont)

def makeNotePlayer(seq: Sequencer, out: PortInfo
        ) -> Callable[[int, bool], None]:
    """Returns a callable object that plays midi notes on a port."""
    def playNote(note: int, enabled: bool) -> None:
        if enabled:
            seq.sendEvent(NoteOn(0, 0, note, 127), out)
        else:
            seq.sendEvent(NoteOff(0, 0, note, 0), out)
    return playNote

if __name__ == '__main__':
    seq = getSequencer('isokbd')
    out = seq.createOutputPort('out')
    if len(sys.argv) > 1:
        type = sys.argv[1]
        if type == 'wicki':
            keys = makeWickiHayden()
        elif type.startswith('harm'):
            keys = makeHarmonic()
        elif type == 'janko':
            keys = makeJanko()
        elif type == 'thirds':
            keys = makeThirds()
    else:
        keys = makeWickiHayden()
    win = IsoKbdWin(keys, playNote=makeNotePlayer(seq, out))
    win.mainloop()

