#==============================================================================
#
#  $Id$
#
"""
   Classes for reading and writing midifiles.
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
#  Revision 1.3  1999-08-26 23:57:54  mike
#  Fixed check for "no more tracks"
#
#  Revision 1.2  1999/08/25 20:23:34  mike
#  Makes a half-assed attempt at dealing with PPQN and tempo.
#
#  Revision 1.1  1999/08/23 17:42:15  mike
#  Classes for reading and writing midifiles.
#
#
#==============================================================================

from midi import SysEx, TrackCursor, StreamReader, Track, Piece
import string, struct
from io import StringIO

class Writer:
   
   def __init__(self, file):
      self.file = file
   
   def writeMThd(self, format, tracks, rate):
      self.file.write(struct.pack('>4sihhh', 'MThd', 6, format, tracks, rate))
   
   def writeMTrk(self, trackData):
      self.file.write(struct.pack('>4si', 'MTrk', len(trackData)))
      self.file.write(trackData)
   
   def encodeVarLen(self, num):
      data = []
      while num or not data:
         data.insert(0, num & 0x7F)
         num = num >> 7
         
      for i in range(len(data) - 1):
         data[i] = data[i] | 0x80
      data = bytes(data)
      return data
   
   def encodeTrackName(self, name):
      return struct.pack('BBB', 0, 0xFF, 3) + \
         self.encodeVarLen(len(name)) + name
   
   def encodeEvents(self, track):
      status = 0
      lastTime = 0
      buffer = b''
      cur = TrackCursor(track)
      while cur.hasMoreEvents():
         evt = cur.nextEvent()
         buffer = buffer + self.encodeVarLen(evt.time - lastTime)
         lastTime = evt.time
         status, data = evt.asMidiString(status)
         if isinstance(evt, SysEx):
            data = data[0] + self.encodeVarLen(len(data) - 1) + data[1:]
         buffer = buffer + data
         
      # add the "end of track" event
      buffer = buffer + struct.pack('BBBB', 0, 0xFF, 0x2F, 0)
      return buffer
   
   def encodeTrack(self, track):
      buffer = self.encodeTrackName(track.name)
      return buffer + self.encodeEvents(track)
   
   def writePiece(self, piece):
      tracks = piece.getTracks()
      self.writeMThd(1, len(tracks), 50)
      for track in tracks:
         trackData = self.encodeTrack(track)
         self.writeMTrk(trackData)

class ParseError(Exception):
   """
      Raised when something bogus is encountered while reading a midi file.
   """
   pass

class Reader(StreamReader):
   
   def __init__(self, file):
      StreamReader.__init__(self)
      self.file = file
      self.__trackNum = 0
      self.__trackName = ''
      self.__piece = None
      self.__gotEvent = 0
      self.__ppqn = 50.0
#      self.__tempo = 20833.3333333
      self.__tempo = 500000.0
   
   def readLen(self):
      return struct.unpack('>I', self.file.read(4))[0]

   def readVarLen(self, track, cur):
      byte = ord(track[cur])
      cur = cur + 1
      val = 0
      while byte & 0x80:
         val = val << 7 | byte & 0x7F
         byte = ord(track[cur])
         cur = cur + 1
      val = val << 7 | byte
      return val, cur

   def _eventRead(self, event):
      """
         Overrides @`midi.StreamReader._eventRead()` so that we can 
         intercept the points at which there should be a timestamp.
      """
      self.__gotEvent = 1

   def computeTrackName(self):
      if self.__trackName:
         name = self.__trackName
      else:
         name = 'Track %d' % self.__trackNum
      
      # make sure that the name is unique
      ext = ''
      i = 0
      while 1:
         fullName = name + ext
         try:
            self.__piece.getTrack(fullName)
         except KeyError:
            name = fullName
            break
         ext = '.%d' % i
         i = i + 1
         
      return name

   def parseSpecialCommand(self, track, cur):
      # ignore the 0xFF
      cur = cur + 1
      
      # get the command
      cmd = ord(track[cur])
      cur = cur + 1
      
      # get the length
      dataLen, cur = self.readVarLen(track, cur)
      
      # get the data
      data = track[cur:cur + dataLen]
      cur = cur + dataLen
      
      if cmd == 3:
         self.__trackName = data
      elif cmd == 0x51:
         self.__tempo = struct.unpack('>I', '\0' + data)[0]
      
      print('got special command %02x of size %d with data %s' % \
         (cmd, dataLen, data))
      return cur

   def parseTrack(self, track, trackName = None):
      status = 0
      cur = 0
      trackLen = len(track)
      lastTime = 0
      while cur < trackLen:
         # read the timestamp
         time, cur = self.readVarLen(track, cur)
         time = lastTime + time
         lastTime = time
         time = self.__cvtTime(lastTime)
#         print 'got time: %d converting to %d' % (lastTime, time)
         
         # read the event
         while not self.__gotEvent:
            cmd = ord(track[cur])
            
            # check for one of the "file-only" commands
            if cmd == 0xFF:
               cur = self.parseSpecialCommand(track, cur)
               break
            
            self._processCmd(time, cmd)
            cur = cur + 1
            if cmd == 0xF0:
               bogus, cur = self.readVarLen(track, cur)
               
         self.__gotEvent = 0
         
      track = Track(name = trackName or self.computeTrackName(),
                    events = self._inputEvents
                    )
      self._inputEvents = []
      return track

   def readTrack(self):
      self.__trackName = ''
      chunkType = self.file.read(4)
      if chunkType == 'MTrk':
         len = self.readLen()
         track = self.file.read(len)
         return self.parseTrack(track)
      elif not chunkType:
         return None
      else:
         raise ParseError('Unexpected chunk type: %s' % chunkType)
   
   def readPiece(self):
      self.__piece = Piece()
      chunkType = self.file.read(4)
      if chunkType == 'MThd':
         len = self.readLen()
         if len != 6:
            raise ParseError('MThd of unexpected size %d' % len)
         format, tracks, rate = \
            struct.unpack('>hhh', self.file.read(6))

         # at this point, we reject the special, negative rate values.
         if rate < 0:
            raise ParseError('Can not deal with SMPTE units')            
         
         self.__ppqn = float(rate)
         
         while 1:
            track = self.readTrack()
            if track is None:
               break
            self.__piece.addTrack(track)
            self.__trackNum = self.__trackNum + 1
         
         return self.__piece            
         
      else:
         raise ParseError('Unexpected chunk type: %s' % chunkType)
   
   
   def __cvtTime(self, time):
#      return int((float(time) / self.__ppqn * 24 * self.__tempo) / 10000.0)
      return int((float(time) * self.__tempo / self.__ppqn) / 10000.0)

def serializeTrack(track):
   """
      Returns the track serialized to a string.
      
      parms:
         track: [midi.Track]
   """
   out = StringIO()
   writer = Writer(out)
   return writer.encodeEvents(track)

def readTrack(serializedTrack, trackName):
   """
      Returns a Track object parsed from serializedTrack.
      
      parms:
         serializedTrack: [str]
         trackName: [str] the name to use for the track.
   """
   return Reader(None).parseTrack(serializedTrack, trackName)
