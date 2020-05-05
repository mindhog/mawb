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

from amidi import getSequencer
from midi import Event as MidiEvent, NoteOn, NoteOff
from tkinter import BOTH, Event, EventType, Frame, Canvas, NSEW, Text, Tk, \
    Toplevel
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

# Wicki-Hayden Layout

keys = {}
start = 30 # the "z" key, which we'll start at G1
for row in rows:
    i = start
    for key in row:
        keys[key] = i
        i += 2

    # Next row starts at the 4th of the previous row (5 semitones)
    start += 5

def defaultNoteFunc(note: int, enabled: bool) -> None:
    print(f'note {note} {enabled and "on" or "off"}')

# Width factor: square root of three.
WFACT = 1.73205

class IsoKbdWin(Frame):

    def __init__(self, playNote: NoteFunc = defaultNoteFunc,
                 toplevel: Union[Tk, Toplevel] = None
                 ):
        if toplevel is None:
            toplevel = Tk()

        super(IsoKbdWin, self).__init__(toplevel)

        self.__canvas = Canvas(self)
        self.__canvas.bind('<KeyPress>', self.on_key_event)
        self.__canvas.bind('<KeyRelease>', self.on_key_event)
        self.__canvas.pack(expand=True, fill = BOTH)
        self.__canvas.focus_set()
        self.__playNote = playNote
        self.pack(expand=True, fill = BOTH)

        self.draw_keyboard(10)

    def on_key_event(self, event: Event) -> Optional[str]:
        ch = keychar(event.keysym)
        poly_id = self.__key_polys.get(ch)
        note_num = keys.get(ch)
        if poly_id is not None:
            if event.type == EventType.KeyPress:
                self.__canvas.itemconfig(poly_id, fill = '#ffffff')
                self.__playNote(note_num, True)
            else:
                self.__canvas.itemconfig(poly_id, fill = '#000000')
                self.__playNote(note_num, False)
            return 'break'
        else:
            print(event.keysym)
            return None

        handler = keys.get(event.keysym)
        print(f'handler is {handler}, key is {event.keysym!r}')
        if handler:
            return handler(event, self.__playNote)
        else:
            return False

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

seq = getSequencer('isokbd')
out = seq.createOutputPort('out')

def playNote(note: int, enabled: bool) -> None:
    if enabled:
        seq.sendEvent(NoteOn(0, 0, note, 127), out)
    else:
        seq.sendEvent(NoteOff(0, 0, note, 0), out)

win = IsoKbdWin(playNote=playNote)
win.mainloop()

