
from abc import abstractmethod, ABC
import os
from queue import Queue
import time

from alsa_midi import SND_SEQ_OPEN_OUTPUT
from amidi import PortInfo, Sequencer
from midi import AllSoundOff, ControlChange, NoteOn, NoteOff, Piece, \
    PitchWheel, ProgramChange, Track
from midifile import Reader as MidiFileReader, Writer as MidiFileWriter
from threading import Thread
from typing import Callable, Optional, Tuple, Union
from tkinter import Canvas, Event, Frame, Label, Tk, Toplevel, PhotoImage, \
    BOTH, NSEW

IMAGE = 'test.png'

ROW_HEIGHT = 10

## Width of the key panel on the left hand side.
KEYS_WIDTH = 40

DEFAULT_NOTE_WIDTH = 40
NOTE_FILL_COLOR = '#ff0000'
POS_MARKER_COLOR = '#ff0000'

NOTE_COLORS = [0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0]
GRID_LINE_COLOR = '#000044'

class AudioIFace(ABC):

    @abstractmethod
    def begin_note_edit(self, note: int, velocity: int) -> None:
        """To be called the first time a note is moved.
        """

    @abstractmethod
    def next_note_edit(self, note: int, velocity: int) -> None:
        """To be called on a subsequent note move.

        It is the responsibility of this interface to do nothing if 'note' has
        not changed since the last time.
        """

    @abstractmethod
    def end_note_edit(self) -> None:
        """To be called when a note edit has ended."""

    @abstractmethod
    def play(self, track: Track):
        """Begin playing."""

    @abstractmethod
    def set_play_callback(self, func: Callable[[int], None]) -> None:
        """Set the callback used to inform the UI of position changes.

        'func' should be callable from any thread, not necessarily just the UI
        thread.  It is passed the current play position (in ticks).
        """

    @abstractmethod
    def set_pos(self, pos: int) -> None:
        """Set the current play position (in ticks)."""

    @abstractmethod
    def stop(self):
        """Stop playing."""

    @abstractmethod
    def isPlaying(self) -> bool:
        """Returns true if the interface is currently playing."""

    @property
    def playing(self) -> bool:
        """Returns true if the interface is currently playing.

        This is just the property form of isPlaying().
        """
        return self.isPlaying()

class MidiEditor(Frame):
    def __init__(self, toplevel: Union[Tk, Toplevel, None] = None,
                 track: Optional[Track] = None,
                 audio: Optional[AudioIFace] = None
                 ):
        super(MidiEditor, self).__init__(toplevel)
        self.__track = Track('track') if track is None else track
        self.__canvas = Canvas(self, background='#000011')
        self.__canvas.grid(row=0, column=1, sticky=NSEW)
        self.__canvas.focus_set()
        self.pack(expand=True, fill=BOTH)
        self.__draw_canvas()

        # Set up the queue.
        self.__queue = Queue()

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

        self.__audio = audio

        toplevel.bind('<space>', self.__toggle_play)

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

        # Render the position line.
        if audio:
            self.__play_callback(0)
            audio.set_play_callback(self.__play_callback)

            self.__pos_marker = self.__canvas.create_line(x, 0, x,
                                                          128 * ROW_HEIGHT,
                                                          fill=POS_MARKER_COLOR
                                                          )


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

        self.after(100, self.__process_queue)

    def __process_queue(self) -> None:
        """Process all events on the queue.

        Then schedule the next queue processing interval.
        """
        while not self.__queue.empty():
            self.__queue.get()()
        self.after(100, self.__process_queue)

    def __draw_pos(self, pos: int) -> None:
        x = pos / self.__ticks_per_x_unit
        self.__canvas.coords(self.__pos_marker, x, 0, x, 128 * ROW_HEIGHT)

    def __play_callback(self, pos: int) -> None:
        # queue a draw_pos call.
        self.__queue.put(lambda: self.__draw_pos(pos))

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
        self.__audio.end_note_edit()

    def __drag(self, id: int, event: Event) -> Optional[str]:
        note = self.__note_from_y(event.y)
        y = (127 - note) * ROW_HEIGHT
        x = event.x - self.__drag_offset[0]
        x1, _, x2, _ = self.__canvas.coords(id)
        self.__canvas.coords(id, x, y, x + x2 - x1, y + ROW_HEIGHT)
        self.__audio.next_note_edit(note, velocity=127)

    def __begin_drag_note(self, id: int, event: Event) -> Optional[str]:
        cx, cy, _, _ = self.__canvas.coords(id)
        self.__drag_offset = (event.x - cx, event.y - cy)
        self.__canvas.tag_bind(id, '<Motion>', lambda e: self.__drag(id, e))
        self.__canvas.tag_bind(id, '<ButtonRelease-1>',
                               lambda e: self.__end_drag(id, e)
                               )

        # xxx look up the original note somehow

        self.__audio.begin_note_edit(self.__note_from_y(cy), velocity=127)
        return 'break'

    def __draw_new_note(self, note: int, t1: int, t2: int) -> int:
        y = self.__y_from_note(note)
        x1 = self.__x_from_time(t1)
        x2 = self.__x_from_time(t2)
        id = self.__canvas.create_rectangle(x1, y, x2, y + ROW_HEIGHT,
                                            fill=NOTE_FILL_COLOR)
        self.__canvas.tag_bind(id, '<Button-1>',
                               lambda e: self.__begin_drag_note(id, e)
                               )
        return id

    def __add_note(self, event: Event) -> Optional[str]:
        # Ignore this if we've started a drag.  It seems that we still get
        # this event even if the handler for the item returns 'break'.
        if self.__drag_offset:
            return

        note = self.__note_from_y(event.y)
        t = self.__time_from_x(event.x)
        self.__audio.begin_note_edit(note, velocity=127)
        self.__draw_new_note(note, t, t + self.__note_len)
        self.__track.add(NoteOn(t, self.__channel, note, self.__velocity))
        self.__track.add(NoteOff(t + self.__note_len, self.__channel, note,
                                 0
                                 )
                         )

    def __end_add_note(self, event: Event) -> None:
        self.__audio.end_note_edit()

    def __toggle_play(self, event: Event) -> None:
        if self.__audio.playing:
            self.__audio.stop()
        else:
            self.__audio.play(self.__track)

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
            self.__canvas.bind('<ButtonRelease-1>', self.__end_add_note)

class MidiEditToplevel(Toplevel):
    """Standalone toplevel for hosting the midi editor."""

    def __init__(self, track: Track, on_save: Callable[[Track], None] = None):
        MidiEditor(self, track)
        if on_save:
            self.bind('<F2>', lambda e: on_save(track))

class AlsaAudioIFace(AudioIFace):

    def __init__(self, seq: Sequencer, port: PortInfo):
        self.seq = seq
        self.port = port
        self.__last_note = -1
        self.__pos = 0
        self.__ticks_per_sec = 48  # need to get this in the parameters
        self.__stopped = True
        self.__callback = None
        self.__thread = None
        self.__track = None

    def begin_note_edit(self, note: int, velocity: int) -> None:
        self.seq.sendEvent(NoteOn(0, 0, note, velocity), self.port)
        self.__last_note = note

    def next_note_edit(self, note: int, velocity: int) -> None:
        if note != self.__last_note:
            self.seq.sendEvent(NoteOff(0, 0, self.__last_note, 0), self.port)
            self.seq.sendEvent(NoteOn(0, 0, note, velocity), self.port)
            self.__last_note = note

    def end_note_edit(self) -> None:
        if self.__last_note == -1:
            return
        self.seq.sendEvent(NoteOff(0, 0, self.__last_note, 0), self.port)
        self.__last_note = -1

    def __run(self) -> None:
        try:
            # start time is the time when the beginning of the track started
            start_time = time.time() - self.__pos / self.__ticks_per_sec

            # 't' is current time in ticks.
            t = self.__pos
            for event in self.__track:
                # Wait for the next event, doing a notification callback
                # periodically.
                next_event_ticks = event.time
                tps = self.__ticks_per_sec
                while t < next_event_ticks:
                    time.sleep(min((next_event_ticks - t) / tps,
                                   0.25
                                   )
                               )
                    if self.__stopped:
                        return
                    if self.__callback:
                        self.__callback(t)
                    self.__pos = t = (time.time() - start_time) * tps
                if isinstance(event, (NoteOn, NoteOff, ControlChange,
                                      ProgramChange, PitchWheel
                                      )
                              ):
                    self.seq.sendEvent(event, self.port)
        finally:
            for channel in range(16):
                self.seq.sendEvent(AllSoundOff(0, channel), self.port)

    def play(self, track: Track) -> None:
        self.__pos = 0
        if not self.__stopped:
            return
        self.__stopped = False
        self.__track = track
        Thread(target=self.__run).start()

    def set_play_callback(self, func: Callable[[int], None]) -> None:
        self.__callback = func

    def set_pos(self, pos: int) -> None:
        self.__pos = pos

    def stop(self) -> None:
        self.__stopped = True

    def isPlaying(self) -> bool:
        return not self.__stopped

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
            i += 1

    if track is None:
        track = Track('unnamed')

    def save(e: Event) -> None:
        piece = Piece()
        piece.addTrack(track)
        MidiFileWriter(open(filename, 'wb')).writePiece(piece)
    tk = Tk()
    tk.bind('<F2>', save)
    seq = Sequencer(SND_SEQ_OPEN_OUTPUT, 0, name='midiedit')
    port = seq.createOutputPort('out')
    win = MidiEditor(tk, track, AlsaAudioIFace(seq, port))
    win.mainloop()

