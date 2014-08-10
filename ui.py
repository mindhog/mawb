# Initial command-line user-interface.
# Will turn this into a real UI at some point.

from mawb_pb2 import RPC, RECORD, IDLE, PLAY
import socket
import struct
import subprocess
import time
from Tkinter import Frame, Text, Tk

import sys

bindings = '''Key Bindings:
<Space>  Play/Pause.
F5 - record.
F3 - quit.
'''

class Comm:

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.sock.connect(('127.0.0.1', 8193))

    def sendRPC(self, **kwargs):
        rpc = RPC()
        if 'set_ticks' in kwargs:
            rpc.set_ticks.append(kwargs['set_ticks'])
        if 'change_sequencer_state' in kwargs:
            rpc.change_sequencer_state = kwargs['change_sequencer_state']
        if 'echo' in kwargs:
            rpc.echo = kwargs['echo']
        if 'save_state' in kwargs:
            rpc.save_state = kwargs['save_state']
        if 'load_state' in kwargs:
            rpc.load_state = kwargs['load_state']
        parcel = rpc.SerializeToString()
        data = struct.pack('<I', len(parcel)) + parcel
        self.sock.send(data)

class Output:

    def __init__(self, text):
        self.text = text

    def info(self, message):
        self.text.insert('end', str(message) + '\n', 'info')

class Commands:

    def __init__(self, comm):
        self.comm = comm
        self.playing = False
        self.out = None

    def togglePlay(self, event):
        if not self.playing:
            self.comm.sendRPC(change_sequencer_state = PLAY)
            self.playing = True
            self.out.info('playing')
        else:
            self.comm.sendRPC(change_sequencer_state = IDLE)
            self.playing = False
            self.out.info('paused')
        return 'break'

    def restart(self, event):
        self.comm.sendRPC(set_ticks = 0)
        self.out.info('set to 0')
        return 'break'

    def record(self, event):
        self.comm.sendRPC(set_ticks = 0, change_sequencer_state = RECORD)
        self.out.info('recording')
        return 'break'

class MyWin(Frame):

    def __init__(self, top, commands):
        Frame.__init__(self, top)
        self.text = Text(self)
        self.text.grid()
        commands.out = Output(self.text)
        self.bindCommands(commands)
        self.grid()

    def bindCommands(self, commands):
        self.text.insert('insert', bindings)
        self.text.bind('<Key-space>', commands.togglePlay)
        self.text.bind('<F5>', commands.record)
        self.text.bind('<F7>', commands.restart)
        self.text.bind('<F3>', self.shutdown)
        self.text.bind('<F1>', self.help)
        self.text.tag_configure('info', foreground = 'green')

    def shutdown(self, event):
        self.quit()

    def help(self, event):
        self.text.insert('end', 'yep.  got help')

class DaemonManager:

    def __init__(self):
        self.daemon = None

    def start(self):
        if self.daemon:
            print 'Daemon already started.'
            return
        self.daemon = subprocess.Popen(['/home/mmuller/w/awb++/awbd'])
        time.sleep(2)

    def stop(self):
        if self.daemon:
            self.daemon.kill()
            self.daemon.wait()
            self.daemon = None
        else:
            print 'Daemon not started.'

    def __del__(self):
        if self.daemon:
            self.stop()

def run():
    daemon = DaemonManager()
    daemon.start()


    # Stuff that should clearly be elsewhere.
    subprocess.call(['aconnect', '130:0', '129:1'])
    subprocess.call(['jack_connect', 'fluidsynth:l_00', 'system:playback_1'])
    subprocess.call(['jack_connect', 'fluidsynth:r_00', 'system:playback_2'])

    comm = Comm()
    commands = Commands(comm)
    win = MyWin(Tk(), commands)
    win.mainloop()

run()
