
from StringIO import StringIO

from mawb_pb2 import PBTrack, RPC, RECORD, IDLE, PLAY
import socket
import struct
import subprocess
import sys
import time
import unittest

import midi as m
import midifile as mf

debug = False

class Test(unittest.TestCase):
    def startDaemon(self):
        awbdCommand = ['./awbd']
        if debug:
            awbdCommand.insert(0, 'gdb')

        self.daemon = subprocess.Popen(awbdCommand)
        time.sleep(1)
        if debug:
            # Bind to a socket so the user can notify us when the daemon has
            # been started.
            self.debug_socket = s = \
                socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
            s.bind(('localhost', 9191))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.listen(5)
            s.accept()
        subprocess.call(['jack_connect', 'fluidsynth:l_00', 'system:playback_1'])
        subprocess.call(['jack_connect', 'fluidsynth:r_00', 'system:playback_2'])

        # Create the connection to the server.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)

    def setUp(self):
        self.startDaemon()

    def tearDown(self):
        self.daemon.kill()

    def sendCommand(self, rpc):
        parcel = rpc.SerializeToString()
        data = struct.pack('<I', len(parcel)) + parcel

        self.sock.connect(('127.0.0.1', 8193))
        self.sock.send(data)

    def makeMidiTrack(self):
        track = m.Track()
        for i in range(4):
            track.add(m.NoteOn(i * 100, 0, 48 + i, 127))
            track.add(m.NoteOff((i + 1) * 100, 0, 48 + i, 127))

        out = StringIO()
        writer = mf.Writer(out)
        return writer.encodeEvents(track)

    def testAddTrack(self):
        rpc = RPC()
        rpc.set_ticks.append(0)
        track = rpc.add_track
        track.events = self.makeMidiTrack()
        rpc.change_sequencer_state = PLAY
        self.sendCommand(rpc)
        time.sleep(5)

unittest.main()

#if command == 'record':
#    rpc.set_ticks.append(0)
#    rpc.change_sequencer_state = RECORD
#elif command == 'stop':
#    rpc.change_sequencer_state = IDLE
#elif command == 'play':
#    rpc.set_ticks.append(0)
#    rpc.change_sequencer_state = PLAY
#elif command == 'echo':
#    rpc.echo.append('test of RPC interface')
#elif command == 'save':
#    rpc.save_state = 'noname.mawb'
#elif command == 'load':
#    rpc.load_state = 'noname.mawb'
