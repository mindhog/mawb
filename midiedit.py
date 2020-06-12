
import os

from midi import NoteOn, NoteOff, Piece, Track
from midifile import Reader as MidiFileReader, Writer as MidiFileWriter
from typing import Callable, Optional, Tuple, Union
from tkinter import Canvas, Event, Frame, Label, Tk, Toplevel, PhotoImage, \
    BOTH, NSEW

IMAGE = 'test.png'

ROW_HEIGHT = 10

## Width of the key panel on the left hand side.
KEYS_WIDTH = 40

DEFAULT_NOTE_WIDTH = 40
NOTE_FILL_COLOR = '#ff0000'

NOTE_COLORS = [0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0]
GRID_LINE_COLOR = '#000044'

class MidiEditor(Frame):
    def __init__(self, toplevel: Union[Tk, Toplevel, None] = None,
                 track: Optional[Track] = None
                 ):
        super(MidiEditor, self).__init__(toplevel)
        self.__track = Track('track') if track is None else track
        self.__canvas = Canvas(self, background='#000011')
        self.__canvas.grid(row=0, column=1, sticky=NSEW)
        self.__canvas.focus_set()
        self.pack(expand=True, fill=BOTH)
        self.__draw_canvas()

        self.__key_canvas = Canvas(self, width=KEYS_WIDTH)
        self.__key_canvas.grid(row=0, column=0, sticky=NSEW)
        for i in range(0, 128):
            y = (127 - i) * ROW_HEIGHT
            color = '#000000' if NOTE_COLORS[i % 12] else '#ffffff'
            self.__key_canvas.create_rectangle(0, y, KEYS_WIDTH, y + ROW_HEIGHT,
                                               fill=color,
                                               outline='#000044')

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Offset from the note position to the mouse position at the start of
        # the drag.
        self.__drag_offset : Optional[Tuple[int, int]] = None

        # "Pulses per beat" (usually "Pulses per quarter note.")
        self.__ppb : int = self.__track.ppqn

        # The current default note length, channel and velocity for new notes.
        self.__note_len : int = self.__ppb
        self.__channel : int = 0
        self.__velocity : int = 127

        # The desired width of a beat ("quarter note") in screen pixels.
        self.__beat_width : float = 40.0

        # Time signature, expressed as beats per measure.
        self.__sig : int = 4

        # The number of midi clock ticks ("pulses") per x axis unit on the
        # screen.
        self.__ticks_per_x_unit : float = self.__ppb / self.__beat_width

        # Render the measure lines.
        measure = self.__ppb * self.__sig
        end_time = track[-1].time if track else (measure * 20)
        t = measure
        while t < end_time + measure:
            x = self.__x_from_time(t)
            self.__canvas.create_line(x, 0, x, 128 * ROW_HEIGHT,
                                      fill=GRID_LINE_COLOR
                                      )
            t += measure

        # Render the notes in the initial track.
        active = {}
        for note in track:
            if isinstance(note, NoteOn):
                active[note.note] = note
            elif isinstance(note, NoteOff):
                try:
                    start = active.pop(note.note)
                    self.__draw_new_note(note.note, start.time, note.time)
                except KeyError:
                    print('Unmatched end note: %s' % note.note)

    def __save_track(self, event: Event):
        """Saves the track. REMOVE THIS"""
        print('that is all')
        piece = Piece()
        piece.addTrack(self.__track)
        MidiFileWriter(open('unnamed.mid', 'wb')).writePiece(piece)

    def __note_from_y(self, y: int) -> int:
        return int(127 - y // ROW_HEIGHT)

    def __y_from_note(self, note: int) -> float:
        return -(note - 127) * ROW_HEIGHT

    def __time_from_x(self, x: int) -> int:
        """Returns the time for a given x coordinate.

        Time is measured in ticks since the beginning of the track.
        """
        return int(x * self.__ticks_per_x_unit)

    def __x_from_time(self, t: int) -> int:
        return int(t / self.__ticks_per_x_unit)

    def __end_drag(self, id: int, event: Event) -> Optional[str]:
        self.__canvas.tag_unbind(id, '<Motion>')
        self.__canvas.tag_unbind(id, '<ButtonRelease-1>')
        self.__drag_offset = None

    def __drag(self, id: int, event: Event) -> Optional[str]:
        y = (127 - self.__note_from_y(event.y)) * ROW_HEIGHT
        x = event.x - self.__drag_offset[0]
        x1, _, x2, _ = self.__canvas.coords(id)
        self.__canvas.coords(id, x, y, x + x2 - x1, y + ROW_HEIGHT)

    def __begin_drag_note(self, id: int, event: Event) -> Optional[str]:
        cx, cy, _, _ = self.__canvas.coords(id)
        self.__drag_offset = (event.x - cx, event.y - cy)
        self.__canvas.tag_bind(id, '<Motion>', lambda e: self.__drag(id, e))
        self.__canvas.tag_bind(id, '<ButtonRelease-1>',
                               lambda e: self.__end_drag(id, e)
                               )
        return 'break'

    def __draw_new_note(self, note: int, t1: int, t2: int) -> None:
        y = self.__y_from_note(note)
        x1 = self.__x_from_time(t1)
        x2 = self.__x_from_time(t2)
        id = self.__canvas.create_rectangle(x1, y, x2, y + ROW_HEIGHT,
                                            fill=NOTE_FILL_COLOR)
        self.__canvas.tag_bind(id, '<Button-1>',
                               lambda e: self.__begin_drag_note(id, e)
                               )


    def __add_note(self, event: Event) -> Optional[str]:
        # Ignore this if we've started a drag.  It seems that we still get
        # this event even if the handler for the item returns 'break'.
        if self.__drag_offset:
            return

        note = self.__note_from_y(event.y)
        t = self.__time_from_x(event.x)
        self.__draw_new_note(note, t, t + self.__note_len)
        self.__track.add(NoteOn(t, self.__channel, note, self.__velocity))
        self.__track.add(NoteOff(t + self.__note_len, self.__channel, note,
                                 0
                                 )
                         )


    def __draw_canvas(self) -> None:
#        photo_image = PhotoImage(file = IMAGE)
#        background_label = Label(self, image=photo_image)
#        background_label.place(x=0, y=0, relwidth=1, relheight=1)
#        self.__canvas.place(x=0, y=0, relwidth=1, relheight=1)

        # draw the grid.
        for i in range(0, 128):
            y = i * ROW_HEIGHT
            #self.__canvas.winfo_width()
            self.__canvas.create_line(0, y, 1000000, y, fill=GRID_LINE_COLOR)
            self.__canvas.bind('<Button-1>', self.__add_note)

class MidiEditToplevel(Toplevel):
    """Standalone toplevel for hosting the midi editor."""

    def __init__(self, track: Track, on_save: Callable[[Track], None] = None):
        MidiEditor(self, track)
        if on_save:
            self.bind('<F2>', lambda e: on_save(track))

if __name__ == '__main__':

    from sys import argv
    track : Optional[Track] = None
    if len(argv) > 1:
        filename = argv[1]
        if os.path.exists(filename):
            piece = MidiFileReader(open(filename, 'rb')).readPiece()
            track = tuple(piece.getTracks())[0]
    else:
        filename = 'unnamed.mid'
        i = 1
        while os.path.exists(filename):
            filename = 'unnamed%s.mid' % i

    if track is None:
        track = Track('unnamed')

    def save(e: Event) -> None:
        piece = Piece()
        piece.addTrack(track)
        MidiFileWriter(open(filename, 'wb')).writePiece(piece)
    tk = Tk()
    tk.bind('<F2>', save)
    win = MidiEditor(tk, track)
    win.mainloop()

