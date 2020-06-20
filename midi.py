#==============================================================================
#
#  $Id$
#
"""
   MIDI sequencer and data model module.
"""
#
#  Copyright (C) 1999 Michael A. Muller
#
#  Permission is granted to use, modify and redistribute this code,
#  providing that the following conditions are met:
#
#  1) This copyright/licensing notice must remain intact.
#  2) If the code is modified and redistributed, the modifications must 
#  include documentation indicating that the code has been modified.
#  3) The author(s) of this code must be indemnified and held harmless
#  against any damage resulting from the use of this code.
#
#  This code comes with ABSOLUTELY NO WARRANTEE, not even the implied 
#  warrantee of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  
#
#  $Log$
#  Revision 1.8  2004-05-22 16:03:43  mike
#  Bunch of changes that I made a long time ago.
#
#  Revision 1.7  1999/09/01 00:17:24  mike
#  Made TrackCursor a SeekableEventSource
#
#  Revision 1.6  1999/08/31 23:08:18  mike
#  Added code to deal with when play is aborted.
#
#  Revision 1.5  1999/08/31 22:42:59  mike
#  Added time offsets and SeekableEventSources so that we can do random-access
#  on MIDI streams.
#
#  Revision 1.3  1999/08/23 17:37:59  mike
#  Added SysEx events, broke out running status processing and midi stream
#  input into StreamReader class, various small fixes.
#
#  Revision 1.1.1.1  1999/07/31 00:04:14  mike
#  MIDI processing software
#
#
#==============================================================================

import struct, os
from select import select
import fcntl

SNDCTL_SEQ_SYNC = 20737
SNDCTL_SEQ_RESET = 20736
SNDCTL_TMR_START = 21506
SNDCTL_TMR_STOP = 21507
SNDCTL_TMR_TIMEBASE = -1073458175	  
SNDCTL_TMR_TEMPO = -1073458171
SNDCTL_SEQ_CTRLRATE = -1073458941

# if this is true, all received midi events will be printed
_printEvents = 0

class Event:
   """
      A MIDI event.  An abstract base class.
      
      Public variables:
      /time/::
         Absolute time of the event.
   """

   def __init__(self, time):
      self.time = time

   def asMidiString(self, status):
      """
         Used to convert the event to a string of bytes suitable for inclusion
         in a midi stream of some sort.  /status/ is the current, running
         status byte.
         
         This method returns a tuple consisting of the new status byte and
         the string representation of the event.
      """
      raise NotImplementedError()

   def __eq__(self, other):
      if self is other:
         return True

      if self.__class__ is not other.__class__:
         return False

      for attr, val in self.__dict__.items():
         if getattr(other, attr, None) != val:
            return False

      return True

class ChannelEvent(Event):
   
   """
      Abstract base class for all events that apply to a particular channel.
      
      Public variables:
      /channel/::
         The channel that the event occurred on.  An integer from 0-15.
   """
   
   def __init__(self, time, channel):
      Event.__init__(self, time)
      self.channel = channel

class NoteEvent(ChannelEvent):
   """
      Base class for midi "note on" and "note off" events, both of which have
      the same public interface.
      
      Public variables:
      /note/::
         Numeric note (0-127)
      /velocity/::
         Numeric velocity (0-127)
   """
   
   def __init__(self, time, channel, note, velocity):
      ChannelEvent.__init__(self, time, channel)
      self.note = note
      self.velocity = velocity

class NoteOn(NoteEvent):
   
   """
      Midi "note on" event.
   """
   
   def asMidiString(self, status):
      if status == 0x90 | self.channel:
         data = struct.pack('BB', self.note, self.velocity)
      else:
         status = 0x90 | self.channel
         data = struct.pack('BBB', status, self.note, self.velocity)
      return status, data
   
   def __str__(self):
      return 'ch: %d, note %d on, velocity %d' % \
             (self.channel, self.note, self.velocity)

   def __repr__(self):
      return 'NoteOn(%s, %s, %s, %s)' % (self.time, self.channel, self.note,
                                         self.velocity
                                         )

class NoteOff(NoteEvent):
   
   """
      Midi "note off" event.
      
      This may be in conflict with the actual midi spec, but I am assuming
      that only a note off with a velocity of 0 can be used in a running
      "note on" status (as a "note on" event with a velocity of 0).  Any
      other velocity value will result in a change in the current status
      to "note off" so that the velocity can be reflected.
   """
   
   def asMidiString(self, status):
      if status == 0x80 | self.channel:
         data = struct.pack('BB', self.note, self.velocity)
      elif status == 0x90 | self.channel and self.velocity == 0:
         data = struct.pack('BB', self.note, 0)
      else:
         status = 0x80 | self.channel
         data = struct.pack('BBB', status, self.note, self.velocity)
      return status, data

   def __str__(self):
      return 'ch: %d, note %d off, velocity %d' % \
             (self.channel, self.note, self.velocity)

   def __repr__(self):
      return 'NoteOff(%s, %s, %s, %s)' % (self.time, self.channel, self.note,
                                         self.velocity
                                         )

class ProgramChange(ChannelEvent):
   
   """
      Midi "program change" event.
    
      Public variables:
      /program/::
         New program number (0-127).
   """
   
   def __init__(self, time, channel, program):
      ChannelEvent.__init__(self, time, channel)
      self.program = program
   
   def asMidiString(self, status):
      # since there is no reason to do running program changes on the same
      # channel, we just always send a status byte.
      status = 0xC0 | self.channel
      return status, struct.pack('BB', status, self.program)

   def __str__(self):
      return 'ch: %d, change to program %d' % \
             (self.channel, self.program)   

   def __repr__(self):
      return 'ProgramChange(%s, %s, %s)' % (self.time, self.channel,
                                            self.program
                                            )

class PitchWheel(ChannelEvent):
   
   """
      Midi "pitch wheel" event.
      
      Public variables:
      /value/::
         Numeric value of the pitch wheel.  A value of 0x2000 is centered.
         Higher values transpose the pitch up, lower values transpose it down.
   """

   def __init__(self, time, channel, value):
      ChannelEvent.__init__(self, time, channel)
      self.value = value
   
   def asMidiString(self, status):
      if status == 0xE0 | self.channel:
         data = struct.pack('BB', self.value & 0x7F, self.value >> 7)
      else:
         status = 0xE0 | self.channel
         data = struct.pack('BBB', status, self.value & 0x7F, self.value >> 7)
      return status, data

   def __str__(self):
      return 'ch: %d, pitch wheel to %d' % \
             (self.channel, self.value)

   def __repr__(self):
      return 'PitchWheel(%s, %s, %s)' % (self.time, self.channel, self.value)

class ControlChange(ChannelEvent):
   
   """
      Midi "control change" event.
      
      Public variables:
      /controller/::
         The controller in question.
      /value/::
         The new value for the controller.
   """
   def __init__(self, time, channel, controller, value):
      ChannelEvent.__init__(self, time, channel)
      self.controller = controller
      self.value = value
   
   def asMidiString(self, status):
      if status == 0xB0 | self.channel:
         data = struct.pack('BB', self.controller, self.value)
      else:
         status = 0xB0 | self.channel
         data = struct.pack('BBB', status, self.controller, self.value)
      return status, data
   
   def __str__(self):
      return 'ch: %d, control %d changed to %d' % \
             (self.channel, self.controller, self.value)

   def __repr__(self):
      return 'ControlChange(%s, %s, %s, %s)' % (self.time, self.channel,
                                                self.controller,
                                                self.value
                                                )

class SysEx(Event):

   """
      Midi "system exclusive" event.  Just a big bag of data passed into
      the system.
      
      Public Variables:
      /data/::
         A string of binary data to be passed into the remote system. 
         The leading F0 and trailing F7 bytes should be omitted: they will
         be generated by the @asMidiString() method.
   """
   
   def __init__(self, time, data):
      Event.__init__(self, time)
      self.data = data
   
   def asMidiString(self, status):
      # XXX not sure if you can do running status with a SysEx event, 
      #     and I'm not taking any chances
      return 0xF0, chr(0xF0) + self.data + chr(0xF7)

   def __str__(self):
      val = ''
      for c in self.data:
         val = val + ' %0x' % c
      return 'SysEx: %s' % val

   def __repr__(self):
      return 'SysEx(%s, %r)' % (self.time, self.data)

class SysRealtime(Event):
   def __init__(self, time):
      Event.__init__(self, time)
   
   def asMidiString(self, status):
      return 0xFA, chr(0xFA)
   
   def __str__(self):
      return self.__class__.__name__

   def __repr__(self):
      return '%s(%s)' % (self.__class__.__name__, self.time)

class SysStart(SysRealtime):
   _code = 0xFA

class SysContinue(SysRealtime):
   _code = 0xFB

class SysStop(SysRealtime):
   _code = 0xFC

# Meta-events.

class SetTempo(Event):

   def __init__(self, time: int, tempo: int):
      super(SetTempo, self).__init__(time)
      self.tempo : int = tempo

   def asMidiString(self, status):
      return 0xFF, struct.unpack(b'BBBBB', 0xFF, 3, self.tempo >> 16,
                                 (self.tempo >> 8) & 0xff,
                                 self.tempo & 0xff
                                 )

   def __str__(self):
      return f'SetTempo: {self.time} {self.tempo}ms/beat'

   def __repr__(self):
      return f'SetTempo({self.time}, {self.tempo})'

class AllSoundOff(ControlChange):

   def __init__(self, time: int, channel: int):
      super(AllSoundOff, self).__init__(time, channel, 120, 0)

class AllNotesOff(ControlChange):

   def __init__(self, time: int, channel: int):
      super(AllNotesOff, self).__init__(time, channel, 123, 0)

# XXX Still need the following classes:
#     AfterTouch
#     ChannelPressure
#     RealTime

class EventSource:
   
   """
      Abstract base class for all event sources.
   """
   
   def __init__(self):
      pass
   
   def hasMoreEvents(self):
      raise NotImplementedError()
   
   def nextEvent(self):
      """
         Returns a *FullEvent* instance for the next available event, returns
         *None* if no more events are available.
      """
      raise NotImplementedError()
   
   def peekNextEvent(self):
      """
         Returns the next event without consuming it.  If there is no
         next event, returns *None*.
      """
      raise NotImplementedError()

class SeekableEventSource(EventSource):

   """
      Abstrack class for event sources that are random access: allowing
      the user to define the position within the event stream as a midi
      clock.
   """
   
   def setPos(self, pos):
      """
         Sets the position within the event stream.  /pos/ is an
         absolute midi clock value.
      """
      raise NotImplementedError()
   
   def getPos(self):
      """
         Returns the position within the event stream as an absolute value.
      """
      raise NotImplementedError()
   
   def getEnd(self):
      """
         Returns the position of the last event in the event stream.
      """
      raise NotImplementedError()

class Track:
   
   """
      A *Track* is a list of events, sorted in order of their time.
      
      Public variables:
      /name/::
         Every track can have an associated name.  If the tracks is part of
         a "piece", use Piece.renameTrack() to rename the track instead
         of setting this attribute directly.
         
         A track name must be unique within the piece.
   """
      
   def __init__(self, name = "", events = [], ppqn = 24):
      """
         /events/ may be used to construct a track with a prefilled
         event list, but the constructor _does not attempt to guarantee
         that /events/ is ordered correctly_.
      """
      # __events is a list of Event objects
      self.__events = events
      self.name = name
      self.ppqn = ppqn
   
   def add(self, event):
      """
         Adds the /event/ (an instance of *Event*) to the track at the given
         time.
      """
      assert isinstance(event, Event)
      if not self.__events:
         self.__events.append(event)
      elif event.time >= self.__events[-1].time:
         self.__events.append(event)
      else:
         i = 0
         for evt in self.__events:
            if evt.time > event.time:
               self.__events.insert(i, event)
               break
            i = i + 1

   def __getitem__(self, index):
      """
         Returns a tuple consisting of the absolute time of the event and the
         event itself at the given /index/ in the event list.
      """
      return self.__events[index]      

   def __len__(self):
      return len(self.__events)
   
   def __iter__(self):
      return iter(self.__events)

   def merge(self, other):
      """
         Returns a new track consisting of the events of /self/ and /other/
         combined.
      """
      source = TrackZipper( [self, other] )
      return Track(self.name, source.getEvents())

   def overwrite(self, other):
      """
         Returns a new track which is the current track overwritten with
         other using a @TrackOverwriter.
      """
      source = TrackOverwriter( [self, other] )
      return Track(self.name, source.getEvents())

   def getChannel(self):
      """
         Returns the channel of the first channel event on the track.
         If there are no channel events on the track, returns *None*.
      """
      for evt in self.__events:
         if isinstance(evt, ChannelEvent):
            return evt.channel
      return None

class TrackZipper(SeekableEventSource):

   def __init__(self, tracks):
      self._events = []
      tracks = map(TrackCursor, tracks)
      event = 1
      
      # build an ordered list of the events in each of the tracks
      while event:
      
         # find the track with the next available event
         event = None
         for track in tracks:
            if track.hasMoreEvents():
               if not event:
                  bestTrack = track
                  event = track.peekNextEvent()
                  continue
                  
               trackEvent = track.peekNextEvent()
               if trackEvent.time < event.time:
                  bestTrack = track
                  event = trackEvent
         
         if event:
            self._addEvent(event, bestTrack, tracks)
            bestTrack.nextEvent()
      
      self.__index = 0
      self.__pos = 0

   def _addEvent(self, event, track, tracks):
      self._events.append(event)
   
   def hasMoreEvents(self):
      return self.__index < len(self._events)
   
   def nextEvent(self):
      if self.__index < len(self._events):
         evt = self._events[self.__index]
         self.__index = self.__index + 1
         try:
            self.__pos = self._events[self.__index].time
         except IndexError:
            self.__pos = evt.time + 1
         return evt
      else:
         return None
   
   def peekNextEvent(self):
      if self._events:
         return self._events[0]
      else:
         return None

   def getEvents(self):
      """
         Returns the entire event list - this is the original, so changing
         it changes the instance.
      """
      return self._events
   
   def getPos(self):
      return self.__pos
   
   def setPos(self, pos):
      self.__pos = pos
      
      # if there are no events, this is not an issue
      if not self._events:
         self.__index = 1
         return
      
      # see if it is later than the last event
      if pos > self._events[-1].time:
         self.__index = len(self._events)
         print('pos is %d, index past the end (%d)' %
               (pos, self._events[-1].time))
         return
      
      # look for it
      for i in range(len(self._events)):
         if pos <= self._events[i].time:
            self.__index = i
            print('setting index to %d' % i)
            break
      else:
         # should never get here
         assert 0 

   def getEnd(self):
      return self._events[-1].time

class TrackOverwriter(TrackZipper):

   """
      This currently implements a "clean-cut" overwriter.  Given a list of two
      tracks, removes all events from the first track which occur during the
      "period of activity" of the second track.  Any NoteOn events which
      are left dangling are turned off at the beginning of this period, 
      any NoteOn events which occur during the period that are not turned off
      during the period are turned on at the end of the period.
   """
   
   def __init__(self, tracks):
      assert len(tracks) == 2
      self.__map = [None] * 128
      self.__done = 0
      TrackZipper.__init__(self, tracks)
   
   def __mapEvent(self, event):
      # store the index of the event that turned them on.
      if isinstance(event, NoteOn):
         self.__map[event.note] = (len(self._events), event.velocity)
         print('mapping note on: %d, %d' % (event.time, event.note))
      elif isinstance(event, NoteOff):
         self.__map[event.note] = None
         print('mapping note off: %d, %d' % (event.time, event.note))
   
   def _addEvent(self, event, track, tracks):
      if track is tracks[0]:
         # keep track of which notes are on and which notes are off,
         self.__mapEvent(event)
         self._events.append(event)
      elif not self.__done:
         # turn off all notes that are currently "on"
         for i in range(len(self.__map)):
            if self.__map[i] is not None:
               self._events.append(NoteOff(event.time, event.channel, i, 0))
               print('truncating %d' % i)
               self.__map[i] = None
         
         # add the new event
         self._events.append(event)
         
         # walk through all events on the first track that occur before the
         # end of the second track, build a map so that we'll know what to
         # turn off.
         
         endTime = track.getTrack()[-1].time
         print('end time %d' % endTime)
         firstTrack = tracks[0]
         while firstTrack.hasMoreEvents():
            e = firstTrack.peekNextEvent()
            if e.time > endTime:
               break
            else:
               self.__mapEvent(e)
               firstTrack.nextEvent()

         # add all of the rest of the events for the track
         while track.hasMoreEvents():
            e = track.nextEvent()
            self._events.append(e)
         
         # turn on all notes that are going to be turned off          
         for i in range(len(self.__map)):
            if self.__map[i] is not None:
               print('starting %d' % i)
               self._events.append(NoteOn(endTime, event.channel, i,
                                          self.__map[i][1]
                                          )
                                   )        
         

class TrackCursor(SeekableEventSource):
   """
      A *TrackCursor* is the means by which we iterate over the set of events
      in a track.
   """

   def __init__(self, track):
      EventSource.__init__(self)
      self.__track = track
      self.__index = 0
      self.__pos = 0

   def hasMoreEvents(self):
      return self.__index < len(self.__track)

   def nextEvent(self):
      event = self.peekNextEvent()
      self.__index = self.__index + 1
      if event:
         self.__pos = event.time
      else:
         self.__pos = self.__track[-1].time + 1
      return event      
   
   def peekNextEvent(self):
      try:
         return self.__track[self.__index]
      except IndexError:
         return None      

   def getTrack(self):
      """
         Returns the associated track.
      """
      return self.__track
   
   def getPos(self):
      return self.__pos
   
   def setPos(self, pos):
      self.__pos = pos
      if pos > self.__track[-1].time:
         self.__index = len(self.__track)
      else:
         for index in range(len(self.__track)):
            if pos <= self.__track[index].time:
               self.__index = index
               break
         else:
            assert 0 # should never get here

   def getEnd(self):
      return self.__track[-1].time   

class Piece:

   """
      A *Piece* is a collection of tracks.
   """
   
   def __init__(self):
      self.__tracks = {}

   def addTrack(self, track):
      self.__tracks[track.name] = track
   
   def getTracks(self):
      return self.__tracks.values()

   def getTrack(self, trackName):
      return self.__tracks[trackName]

   def deleteTrack(self, track):
      """
         Deletes a track from the piece.  /track/ can be either a @Track
         instance or the name of a track.
      """
      if isinstance(track, Track):
         track = track.name
      del self.__tracks[track]

class PieceCursor(TrackZipper):
   
   def __init__(self, piece):
      TrackZipper.__init__(self, piece.getTracks())

class StreamReader:
   """
      Maintains state information for the parsing of midi commands out of
      the sequencer or a midi file.
   """

   # statuses
   NO_STATE = 0
   NOTE_ON = 1
   NOTE_OFF = 2
   SYS_EX = 3
   AFTER_TOUCH = 4
   PROGRAM_CHANGE = 5
   CHANNEL_PRESSURE = 6
   PITCH_WHEEL = 7
   CONTROL_CHANGE = 8

   def __init__(self):
      self.__buf = []
      self.__state = self.NO_STATE
      self.__channel = 0
      
      # list of events being input
      self._inputEvents = []

      # the event filter
      self.__eventFilter = None

   def _processCmd(self, time, cmd):
      evt = None
      extra = 0
      if cmd & 0x80:
         highNyb = cmd & 0xF0
         if highNyb == 0x80:
            self.__state = self.NOTE_OFF
         elif highNyb == 0x90:
            self.__state = self.NOTE_ON
         elif highNyb == 0xA0:
            self.__state = self.AFTER_TOUCH
         elif highNyb == 0xB0:
            self.__state = self.CONTROL_CHANGE
         elif highNyb == 0xC0:
            self.__state = self.PROGRAM_CHANGE
         elif highNyb == 0xD0:
            self.__state = self.CHANNEL_PRESSURE
         elif highNyb == 0xE0:
            self.__state = self.PITCH_WHEEL
         elif cmd == 0xF0:
            self.__state = self.SYS_EX
            self.__buf = ''
         elif cmd == 0xF7:
            evt = SysEx(time, self.__buf)
            self.__buf = []
         
         # change the channel if the status byte has channel information in
         # it
         if highNyb != 0xF0:
            self.__channel = cmd & 0xF
      else:
         if self.__state == self.NOTE_ON:
            if self.__buf:
               if cmd == 0:
                  evt = NoteOff(time, self.__channel, self.__buf[0], 0)
               else:
                  evt = NoteOn(time, self.__channel, self.__buf[0], cmd)
               self.__buf = []
            else:
               self.__buf.append(cmd)
         elif self.__state == self.NOTE_OFF:
            if self.__buf:
               if cmd == 0:
                  evt = NoteOff(time, self.__channel, self.__buf[0], 0)
               else:
                  evt = NoteOn(time, self.__channel, self.__buf[0], cmd)
               self.__buf = []
            else:
               self.__buf.append(cmd)
         elif self.__state == self.PROGRAM_CHANGE:
            evt = ProgramChange(time, self.__channel, cmd)
         elif self.__state == self.PITCH_WHEEL:
            if self.__buf:
               val = self.__buf[0] | (cmd << 7)
               evt = PitchWheel(time, self.__channel, val)
               self.__buf = []
            else:
               self.__buf.append(cmd)
         elif self.__state == self.CONTROL_CHANGE:
            if self.__buf:
               cntrl = self.__buf[0]
               evt = ControlChange(time, self.__channel, cntrl, cmd)
               self.__buf = []
            else:
               self.__buf.append(cmd)
         elif self.__state == self.SYS_EX:
            self.__buf = self.__buf + chr(cmd)
         else:
            # XXX this should effectively ignore everything else
            pass

      if evt:
         self._eventRead(evt)

      if evt and self.__eventFilter:
         oldEvt = evt
         evt = self.__eventFilter(evt)
         if not evt:
            print('event filtered:', oldEvt)
         
      if evt:
         self._inputEvents.append(evt)

   def setEventFilter(self, filter):
      """
         Sets the object or function that is used to translate and filter
	 events that are read from the midi stream.
         
         /filter/ should be a callable object that accepts an @Event
         as a parameter.

         It should return the same event, or a translated event, or *None*
         if the event is to be discarded.
      """
      self.__eventFilter = filter

   def _eventRead(self, event):
      """
         This is a hook that can be used by derived classes to receive
         notification of when a complete event is read.
      """
      pass

class Sequencer(EventSource, StreamReader):
   
   """
      Wrapper class around /dev/sequencer.
   """
   
   
   def __init__(self, device = '/dev/sequencer'):
      StreamReader.__init__(self)
      self.__src = os.open(device, os.O_RDWR | os.O_NONBLOCK, 0)
      
      # the last status byte written
      self.__status = 0
      
      # this is the queue where we store raw data chunks that are ready to
      # be written to the sequencer.
      self.__outputQueue = []
      
      # this is the current source of output events
      self.__outputEvents = None
      
      self.__timeOffset = 0
      
   def __del__(self):
      os.close(self.__src)

   def hasMoreEvents(self):
      pass
      
   def nextEvent(self):
      pass
   
   def peekNextEvent(self):
      pass

   def record(self, control):
      if hasattr(self, '__firstTimeThrough'):
         self.__reset()
      else:
         self.__firstTimeThrough = 1
      self.__resetTime()
      self.__recordOnly(control)

      track = Track(events = self._inputEvents)
      self._inputEvents = []
      return track

   def __playAndRecord(self, control):
      eventSource = self.__outputEvents
      self.__reset()
      if isinstance(eventSource, SeekableEventSource):
         self.__resetTime(eventSource.getPos())
      else:
         self.__resetTime()
      while 1:
         selected = select([self.__src, control], [self.__src], [])
         
         # first check for incoming events
         if self.__src in selected[0]:
            time, cmd = self.__read()
            self._processCmd(time, cmd)
         
         # check to see if the sequencer is ready to accept more events
         elif (self.__outputQueue or eventSource.hasMoreEvents()) \
              and self.__src in selected[1]:
            self.__writeSeqEvent()
#            self.__writeEvent(eventSource.nextEvent())
         
         # otherwise, this is an event from the controller or we have
         # run out of output events
         else:
            if isinstance(eventSource, SeekableEventSource):
               eventSource.setPos(self.__getPos())
            break
      
      # if we terminated with an event from the controller, reset the
      # sequencer
      if control in selected[0]:
         print('resetting')
         self.__reset()
         return 0
      else:
         print(selected)
         return 1

   def playAndRecord(self, eventSource, control):
      self.__outputEvents = eventSource
      if self.__playAndRecord(control):
         # read any remaining events in the input queue
         self.__recordOnly(control)
      
      track = Track(events = self._inputEvents)
      self._inputEvents = []
      return track

   def __writeSeqEvent(self):
      if not self.__outputQueue:
         self.__queueEvent()

      if _printEvents:
         print('%02x %02x %02x %02x' %
               struct.unpack('BBBB', self.__outputQueue[0]))
      
      os.write(self.__src, self.__outputQueue[0])
      del self.__outputQueue[0]
   
   def __queueEvent(self):
      event = self.__outputEvents.nextEvent()
      self.__status, data = event.asMidiString(self.__status)

      time = self.__fixTime(event.time)
      seqEvt = struct.pack('=BHB', 2, time & 0xFFFF,
                           event.time >> 16
                           )
      self.__outputQueue.append(seqEvt)
      
      for cmd in data:
         seqEvt = struct.pack('=BBh', 5, ord(cmd), 0)
         self.__outputQueue.append(seqEvt)

   def play(self, eventSource, control = None):
      self.__outputEvents = eventSource
      if isinstance(eventSource, SeekableEventSource):
         self.__resetTime(eventSource.getPos())
      else:
         self.__resetTime()
      
      if control is not None:
         inputs = [ control ]
      else:
         inputs = []

      self.__outputEvents = eventSource
      eventsWritten = 0
      while 1:
         selected = select(inputs, [self.__src], [])
         
         # check to see if we got an interrupt
         if control is not None and control in selected[0]:
            if isinstance(eventSource, SeekableEventSource):
               eventSource.setPos(self.__getPos())
            self.__reset()
            break
         
         # check to see if the sequencer is ready to accept more events
         elif (self.__outputQueue or eventSource.hasMoreEvents()) \
              and self.__src in selected[1]:
            eventsWritten = eventsWritten + 1
            self.__writeSeqEvent()
         else:
            break
      
      if control is not None:
         self.__syncOrSwim(control)   
      else:
         self.__sync()
         
      print('events written: %d has more: %d' % (eventsWritten, 
                                                 eventSource.hasMoreEvents()))
   
   def __recordOnly(self, control):
      """
         Records events without playing any.
      """
      while 1:
         selected = select([self.__src, control], [], [])
         if self.__src in selected[0]:
            time, cmd = self.__read()
            self._processCmd(time, cmd)
         else:
            self.__reset()
            break

   def __writeEvent(self, event):
      """
         Writes the /event/ to the sequencer.
      """
      self.__status, data = event.asMidiString(self.__status)
      time = self.__fixTime(event.time)
      for cmd in data:
         seqEvt = struct.pack('=BHBBBh',
                              2,
                              time & 0xFFFF,
                              time >> 16,
                              5,
                              ord(cmd),
                              0
                              )
         assert len(seqEvt) == 8
         os.write(self.__src, seqEvt)

   def __read(self):
      """
         Reads the next 8 byte /dev/sequencer event, returns a tuple 
         consisting of timestamp and command ("command" is really just the
         next byte from the midi event stream).
      """
      data = os.read(self.__src, 8)
      code, time, timeHigh, five, cmd, zeroes = struct.unpack('=bHBBBh', data)
      time = self.__fixInputTime(time + (timeHigh << 16))
      return time, cmd
      
   def __reopen(self):
      # XXX not sure if we need this - keeping it around because it's
      # XXX useful for now
      os.close(self.__src)
      self.__src = os.open('/dev/sequencer', os.O_RDWR | os.O_NONBLOCK, 0)

   def __fixTime(self, time):
      return time - self.__timeOffset

   def __fixInputTime(self, time):
      return time + self.__timeOffset

   def __reset(self):
      fcntl.ioctl(self.__src, SNDCTL_SEQ_RESET)
      self.__status = 0

   def __sync(self):
      # write an "ECHO" command (the 8) to the sequencer, then wait for
      # the response (another "ECHO" which will show up when the sequencer
      # is done playing).
      os.write(self.__src, struct.pack('=BHB', 8, 0, 0))
      select([self.__src], [], [])
      data = os.read(self.__src, 4)
      if _printEvents:
         print('%02x %02x %02x %02x' %
               struct.unpack('BBBB', data))

   def __syncOrSwim(self, control):
      # like the sync, but uses a control stream also, doing a reset if
      # input comes from control.
      # XXX this should fail if any other event comes in before the sync,
      #     but it doesn't seem to.
      os.write(self.__src, struct.pack('=BHB', 8, 0, 0))
      selected = select([self.__src, control], [], [])
      if control in selected[0]:
         self.__reset()
      else:
         data = os.read(self.__src, 4)
         if _printEvents:
            print('%02x %02x %02x %02x' %
                  struct.unpack('BBBB', data))

   def __resetTime(self, time = 0):
      self.__timeOffset = time
      os.write(self.__src, struct.pack('=BHB', 4, 0, 0))
      self.__systemStartTime = os.times()[4]
   
   def __getPos(self):
      return int((os.times()[4] - self.__systemStartTime) * 100) + \
         self.__timeOffset
   
   def showTimeBase(self):
      timebase = struct.pack('i', 200)
      data = fcntl.ioctl(self.__src, SNDCTL_SEQ_CTRLRATE, timebase)
      print('timebase:', struct.unpack('i', timebase), struct.unpack('i', 
                                       data))

programs = [
    'Acoustic Grand Piano',
    'Bright Acoustic Piano',
    'Electric Grand Piano',
    'Honky-tonk Piano',
    'Electric Piano 1',
    'Electric Piano 2',
    'Harpsichord',
    'Clavi',
    'Celesta',
    'Glockenspiel',
    'Music Box',
    'Vibraphone',
    'Marimba',
    'Xylophone',
    'Tubular Bells',
    'Dulcimer',
    'Drawbar Organ',
    'Percussive Organ',
    'Rock Organ',
    'Church Organ',
    'Reed Organ',
    'Accordion',
    'Harmonica',
    'Tango Accordion',
    'Acoustic Guitar (nylon)',
    'Acoustic Guitar (steel)',
    'Electric Guitar (jazz)',
    'Electric Guitar (clean)',
    'Electric Guitar (muted)',
    'Overdriven Guitar',
    'Distortion Guitar',
    'Guitar harmonics',
    'Acoustic Bass',
    'Electric Bass (finger)',
    'Electric Bass (pick)',
    'Fretless Bass',
    'Slap Bass 1        ',
    'Slap Bass 2        ',
    'Synth Bass 1',
    'Synth Bass 2',
    'Violin',
    'Viola',
    'Cello',
    'Contrabass',
    'Tremolo Strings',
    'Pizzicato Strings',
    'Orchestral Harp',
    'Timpani',
    'String Ensemble 1',
    'String Ensemble 2',
    'SynthStrings 1',
    'SynthStrings 2',
    'Choir Aahs',
    'Voice Oohs',
    'Synth Voice',
    'Orchestra Hit',
    'Trumpet',
    'Trombone',
    'Tuba',
    'Muted Trumpet',
    'French Horn',
    'Brass Section',
    'SynthBrass 1',
    'SynthBrass 2',
    'Soprano Sax',
    'Alto Sax',
    'Tenor Sax',
    'Baritone Sax',
    'Oboe',
    'English Horn',
    'Bassoon',
    'Clarinet',
    'Piccolo',
    'Flute',
    'Recorder',
    'Pan Flute',
    'Blown Bottle',
    'Shakuhachi',
    'Whistle',
    'Ocarina',
    'Lead 1 (square)',
    'Lead 2 (sawtooth)',
    'Lead 3 (calliope)',
    'Lead 4 (chiff)',
    'Lead 5 (charang)',
    'Lead 6 (voice)',
    'Lead 7 (fifths)',
    'Lead 8 (bass + lead)',
    'Pad 1 (new age)',
    'Pad 2 (warm)',
    'Pad 3 (polysynth)',
    'Pad 4 (choir)',
    'Pad 5 (bowed)',
    'Pad 6 (metallic)',
    'Pad 7 (halo)',
    'Pad 8 (sweep)',
    'FX 1 (rain)',
    'FX 2 (soundtrack)',
    'FX 3 (crystal)',
    'FX 4 (atmosphere)',
    'FX 5 (brightness)',
    'FX 6 (goblins)',
    'FX 7 (echoes)',
    'FX 8 (sci-fi)',
    'Sitar',
    'Banjo',
    'Shamisen',
    'Koto',
    'Kalimba',
    'Bag pipe',
    'Fiddle',
    'Shanai',
    'Tinkle Bell',
    'Agogo',
    'Steel Drums',
    'Woodblock',
    'Taiko Drum',
    'Melodic Tom',
    'Synth Drum',
    'Reverse Cymbal',
    'Guitar Fret Noise',
    'Breath Noise',
    'Seashore',
    'Bird Tweet',
    'Telephone Ring',
    'Helicopter',
    'Applause',
    'Gunshot',
]

'''         
import sys
seq = Sequencer()
print 'recording track1'
track1 = seq.record(sys.stdin)
track1.name = 'track 1'
sys.stdin.readline()

print 'playing track 1'
seq.play(TrackCursor(track1))

print 'playing piece'
piece = Piece()
piece.addTrack(track1)
seq.play(PieceCursor(piece))
sys.exit(0)

print 'recording track2'
track2 = seq.playAndRecord(TrackCursor(track1), sys.stdin)
track2.name = 'track 2'
sys.stdin.readline()

piece = Piece()
piece.addTrack(track1)
piece.addTrack(track2)

#print 'test run'
#seq.playAndRecord(PieceCursor(piece), sys.stdin)
#sys.stdin.readline()

print 'playing both'
seq.play(PieceCursor(piece))


"""
   There seems to be something wrong with the PieceCursor.
"""
'''