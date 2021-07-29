
from abc import abstractmethod, ABC
from enum import Enum
import os
from queue import Queue
import select
import time

from alsa_midi import SND_SEQ_OPEN_OUTPUT, SND_SEQ_OPEN_INPUT
from amidi import PortInfo, Sequencer
from midi import AllSoundOff, ControlChange, Event as MIDIEvent, NoteOn, \
    NoteOff, Piece, PitchWheel, ProgramChange, SetTempo, Track, TrackCursor
from midifile import Reader as MidiFileReader, Writer as MidiFileWriter
from threading import Thread
from typing import Callable, Optional, Tuple, Union
from tkinter import Canvas, Event, Frame, Label, Scrollbar, Tk, Toplevel, \
    PhotoImage, BOTH, HORIZONTAL, VERTICAL, NSEW

ROW_HEIGHT = 10

## Width of the key panel on the left hand side.
KEYS_WIDTH = 40

DEFAULT_NOTE_WIDTH = 40
NOTE_FILL_COLOR = '#00ff00'
POS_MARKER_COLOR = '#ff0000'

NOTE_COLORS = [0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0]
GRID_LINE_COLOR = '#000044'

# The outline color of notes.
SELECT_OUTLINE = 'white'
NORMAL_OUTLINE = 'black'

class DragMode(Enum):
    NONE = 0    # Not dragging.
    MOVE = 1    # Move a note to a different note or position
    EXTEND = 2  # Make the note longer or shorter or start earlier/later

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
    def set_event_recorder(self, func: Callable[[MIDIEvent], None]) -> None:
        """Set a function to be called when a new event comes in during play.
        """

    @abstractmethod
    def set_pos(self, pos: int) -> None:
        """Set the current play position (in ticks)."""

    @abstractmethod
    def get_pos(self) -> int:
        """Return the current play position (in ticks)."""

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

        hsb = Scrollbar(self, orient=HORIZONTAL, command=self.__canvas.xview)
        hsb.grid(row=1, column=1, sticky=NSEW)
        vsb = Scrollbar(self, orient=VERTICAL, command=self.__canvas.yview)
        vsb.grid(row=0, column=2, sticky=NSEW)

        self.__canvas.config(xscrollcommand=hsb.set, yscrollcommand=vsb.set)

        # Set up the queue.  This is to allow background threads to post
        # changes to the Tk thread.
        self.__queue : 'Queue[Callable[[], Any]]' = Queue()

        # A mapping from the ids of the widgets that represent notes to the
        # list of note events that comprise them.
        # At present, there will usually be exactly two events in this list.
        # However, if support for aftertouch events are added, they will
        # likely be included in this list, too.
        self.__note_map : Dict[int, List[Event]] = {}

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

        # Drag parameters.

        # Offset from the note position to the mouse position at the start of
        # the drag.
        self.__drag_offset : Optional[Tuple[int, int]] = None

        # X position at the start of the drag.
        self.__drag_org_x : int = 0

        # Current drag mode.
        self.__drag_mode : DragMode = DragMode.NONE

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

        # Key bindings.  We have to bind these to the toplevel, the frame
        # won't intercept them.
        toplevel.bind('<space>', self.__toggle_play)
        toplevel.bind('<Left>', self.__left_note)
        toplevel.bind('<Right>', self.__right_note)

        # Render the note and measure lines.
        measure = self.__ppb * self.__sig
        note = self.__ppb
        end_time = track[-1].time if track else (measure * 20)
        t = note
        while t < end_time + measure:
            x = self.__x_from_time(t)
            self.__canvas.create_line(x, 0, x, 128 * ROW_HEIGHT,
                                      fill=GRID_LINE_COLOR,
                                      dash=(3, 3) if t % measure else None
                                      )
            t += note

        self.__canvas.config(scrollregion=(0, 0, self.__x_from_time(end_time),
                                           128 * ROW_HEIGHT
                                           )
                             )
        self.__canvas.bind('<Delete>', self.__delete_selected)

        # Render the position line.
        if audio:
            self.__play_callback(0)
            audio.set_play_callback(self.__play_callback)
            audio.set_event_recorder(self.get_event_recorder())

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
                    id = self.__draw_new_note(start.note, start.time,
                                              note.time)
                    self.__note_map[id] = [start, note]
                except KeyError:
                    print('Unmatched end note: %s' % note.note)

        self.after(100, self.__process_queue)

    # Position Navigation functions

    def __left_note(self, event: Event):
        """Move the play-head one beat left (back in time)."""
        pos = self.__audio.get_pos()
        if not pos:
            # Do nothing if we're already at zero.
            return

        if pos % self.__ppb:
            # between two notes, quantify to the previous one.
            pos = pos // self.__ppb * self.__ppb
        else:
            pos = (pos // self.__ppb - 1) * self.__ppb
        self.__audio.set_pos(pos)

    def __right_note(self, event: Event):
        """Move the play-head one beat right (forward in time)."""
        self.__audio.set_pos(
            (self.__audio.get_pos() // self.__ppb + 1) * self.__ppb
        )

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

    def __select_single(self, id: int) -> None:
        """Select a single note, unselect current selections."""
        self.__canvas.itemconfigure('selected', outline=NORMAL_OUTLINE)
        self.__canvas.dtag('selected', 'selected')
        self.__canvas.itemconfigure(id, tags=['selected'],
                                    outline=SELECT_OUTLINE)


    def __toggle_select(self, id: int) -> None:
        """Toggle the selection status of a given element."""
        tags = self.__canvas.gettags(id)
        if 'selected' in tags:
            self.__canvas.dtag(id, 'selected')
            self.__canvas.itemconfigure(id, outline=NORMAL_OUTLINE)
        else:
            self.__canvas.itemconfigure(id, tags=['selected'],
                                        outline=SELECT_OUTLINE)

    def __delete_selected(self, event: Event):
        """Delete all selected notes."""
        for item in self.__canvas.find_withtag('selected'):
            for midi_event in self.__note_map[item]:
                self.__track.remove(midi_event)
            del self.__note_map[item]
            self.__canvas.delete(item)

    def __get_x(self, event: Event) -> int:
        """Returns the x coordinate for an event's screen y coordinate."""
        return int(self.__canvas.canvasx(event.x))

    def __get_y(self, event: Event) -> int:
        """Returns the y coordinate for an event's screen y coordinate."""
        return int(self.__canvas.canvasy(event.y))

    def __end_drag(self, id: int, event: Event) -> Optional[str]:
        self.__canvas.tag_unbind(id, '<Motion>')
        self.__canvas.tag_unbind(id, '<ButtonRelease-1>')
        self.__audio.end_note_edit()

        if self.__drag_mode == DragMode.MOVE:
            # Move the original events to the new time and note.
            note = self.__note_from_y(self.__get_y(event))
            t = self.__time_from_x(self.__get_x(event) - self.__drag_offset[0])
            events = self.__note_map[id]
            start_time = events[0].time
            for event in events:
                if isinstance(event, (NoteOn, NoteOff)):
                    event.note = note
                if t != start_time:
                    event.time = t + event.time - start_time
                    self.__track.reposition(event)
        elif self.__drag_mode == DragMode.EXTEND:
            length = self.__get_x(event) - self.__drag_org_x
            events = self.__note_map[id]
            events[1].time += self.__time_from_x(length)
            self.__track.reposition(events[1])

        self.__drag_mode = DragMode.NONE
        self.__drag_offset = None
        self.__drag_org_x = 0

    def __drag(self, id: int, event: Event) -> Optional[str]:
        if self.__drag_mode == DragMode.MOVE:
            note = self.__note_from_y(self.__get_y(event))
            y = (127 - note) * ROW_HEIGHT
            x = self.__get_x(event) - self.__drag_offset[0]
            x1, _, x2, _ = self.__canvas.coords(id)
            self.__canvas.coords(id, x, y, x + x2 - x1, y + ROW_HEIGHT)
            self.__audio.next_note_edit(note, velocity=127)
        elif self.__drag_mode == DragMode.EXTEND:
            length = self.__get_x(event) - self.__drag_org_x
            x1, y1, x2, y2 = self.__canvas.coords(id)
            events = self.__note_map[id]
            org_len = self.__x_from_time(events[1].time - events[0].time)
            if length + org_len > 0:
                self.__canvas.coords(id, x1, y1, x1 + org_len + length, y2)

    def __begin_drag(self, id: int, event: Event, mode: DragMode) -> None:
        cx, cy, _, _ = self.__canvas.coords(id)
        self.__drag_org_x = self.__get_x(event)
        self.__drag_offset = (self.__get_x(event) - cx, self.__get_y(event) - cy)
        self.__canvas.tag_bind(id, '<Motion>', lambda e: self.__drag(id, e))
        self.__canvas.tag_bind(id, '<ButtonRelease-1>',
                               lambda e: self.__end_drag(id, e)
                               )
        self.__drag_mode = mode

        self.__audio.begin_note_edit(self.__note_from_y(cy), velocity=127)

    def __begin_drag_note(self, id: int, event: Event) -> Optional[str]:
        self.__select_single(id)
        self.__begin_drag(id, event, DragMode.MOVE)
        return 'break'

    def __begin_duration_drag(self, id: int, event: Event) -> Optional[str]:
        self.__select_single(id)
        self.__begin_drag(id, event, DragMode.EXTEND)
        return 'break'

    def __toggle_select_handler(self, id: int, event: Event) -> None:
        # We don't really have any meaningful "drag" semantics to this yet,
        # but it still has a lot of the semmantics of a drag event.
        self.__begin_drag(id, event, DragMode.NONE)
        self.__toggle_select(id)

    def __draw_new_note(self, note: int, t1: int, t2: int) -> int:
        y = self.__y_from_note(note)
        x1 = self.__x_from_time(t1)
        x2 = self.__x_from_time(t2)
        id = self.__canvas.create_rectangle(x1, y, x2, y + ROW_HEIGHT,
                                            fill=NOTE_FILL_COLOR)
        self.__canvas.tag_bind(id, '<Button-1>',
                               lambda e: self.__begin_drag_note(id, e)
                               )
        self.__canvas.tag_bind(id, '<Shift-Button-1>',
                               lambda e: self.__begin_duration_drag(id, e)
                               )
        self.__canvas.tag_bind(id, '<Control-Button-1>',
                               lambda e: self.__toggle_select_handler(id, e)
                               )
        return id

    def __add_note(self, event: Event) -> Optional[str]:
        # Ignore this if we've started a drag.  It seems that we still get
        # this event even if the handler for the item returns 'break'.
        if self.__drag_offset:
            return

        note = self.__note_from_y(self.__get_y(event))
        t = self.__time_from_x(self.__get_x(event))
        self.__audio.begin_note_edit(note, velocity=127)
        note_on = NoteOn(t, self.__channel, note, self.__velocity)
        note_off = NoteOff(t + self.__note_len, self.__channel, note, 0)
        self.__add_note_pair(note_on, note_off)

    def __add_note_pair(self, note_on: NoteOn, note_off: NoteOff) -> None:
        id = self.__draw_new_note(note_on.note, note_on.time,
                                  note_off.time)
        self.__track.add(note_on)
        self.__track.add(note_off)
        self.__note_map[id] = [note_on, note_off]
        self.__select_single(id)

    def get_event_recorder(self) -> Callable[[MIDIEvent], None]:
        """Returns a function that records midi events.

        The function returned can safely be called from any thread.
        """
        # Keeps track of which notes from the input device have a NoteOn
        # event that hasn't been closed.
        note_map : Dict[int, NoteOn] = {}

        def record_event(event: MIDIEvent):
            # The internal record-event function, that actually stores the
            # event in the track.
            if isinstance(event, NoteOn):
                note_map[event.note] = event
            elif isinstance(event, NoteOff):
                start = note_map.get(event.note)
                if start:
                    self.__add_note_pair(start, event)
                    del note_map[event.note]
            else:
                self.__track.add(event)

        def on_event(event: MIDIEvent):
            # This is the returned record function that is safe to call in a
            # non-ui thread.
            self.__queue.put(lambda: record_event(event))

        return on_event

    def __end_add_note(self, event: Event) -> None:
        self.__audio.end_note_edit()

    def __toggle_play(self, event: Event) -> None:
        if self.__audio.playing:
            self.__audio.stop()
        else:
            self.__audio.play(self.__track)

    def __draw_canvas(self) -> None:
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

    def __init__(self, seq: Sequencer, port: PortInfo, ppb: int):
        self.seq = seq
        self.port = port
        self.__last_note = -1
        self.__pos = 0
        # Start ticks per sec as a bogus value, respond to a SetTempo event
        # while replaying.
        self.__ticks_per_sec = 48
        self.__stopped = True
        self.__callback = None
        self.__record_event = None
        self.__thread = None
        self.__track = None
        self.__ppb = ppb

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

            # Get the input handler to allow us to read midi events.
            input_handle = self.seq.getPollHandle()

            # 't' is current time in ticks.
            t = self.__pos
            cur = TrackCursor(self.__track)
            cur.setPos(t)
            while True:
                event = cur.nextEvent()
                if not event:
                    return

                # Wait for the next event, doing a notification callback
                # periodically.
                next_event_ticks = event.time
                tps = self.__ticks_per_sec
                while t < next_event_ticks:
                    handles = select.select([input_handle], [], [input_handle],
                                            min((next_event_ticks - t) / tps,
                                                0.25
                                                )
                                            )
                    if self.__stopped:
                        return

                    self.__pos = t = int((time.time() - start_time) * tps)

                    # Process all input events.
                    if handles[0]:
                        while self.seq.hasEvent():
                            ev = self.seq.getEvent(t)
                            if isinstance(ev,
                                          (NoteOn, NoteOff, ControlChange,
                                           ProgramChange, PitchWheel)
                                          ):
                                self.seq.sendEvent(ev, self.port)
                                if self.__record_event:
                                    self.__record_event(ev)
                            else:
                                print(f'got unknonwn event {ev}')

                    if self.__callback:
                        self.__callback(t)
                if isinstance(event, (NoteOn, NoteOff, ControlChange,
                                      ProgramChange, PitchWheel
                                      )
                              ):
                    self.seq.sendEvent(event, self.port)
                elif isinstance(event, SetTempo):
                    print(f'usecs per qn {event.tempo}')
                    self.__ticks_per_sec = 1000000 / event.tempo * self.__ppb
        finally:
            for channel in range(16):
                self.seq.sendEvent(AllSoundOff(0, channel), self.port)

    def play(self, track: Track) -> None:
        if not self.__stopped:
            return
        self.__stopped = False
        self.__track = track
        Thread(target=self.__run).start()

    def set_play_callback(self, func: Callable[[int], None]) -> None:
        self.__callback = func

    def set_event_recorder(self, func: Callable[[MIDIEvent], None]) -> None:
        self.__record_event = func

    def set_pos(self, pos: int) -> None:
        self.__pos = pos
        if self.__callback:
            self.__callback(pos)

    def get_pos(self) -> int:
        return self.__pos

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
    seq = Sequencer(SND_SEQ_OPEN_INPUT | SND_SEQ_OPEN_OUTPUT, 0, name='midiedit')
    port = seq.createOutputPort('out')
    seq.createInputPort('in')
    print(f'ppqn = {track.ppqn}')
    win = MidiEditor(tk, track, AlsaAudioIFace(seq, port, track.ppqn))
    win.mainloop()

