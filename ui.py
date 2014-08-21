# Initial command-line user-interface.
# Will turn this into a real UI at some point.

from mawb_pb2 import PBTrack, SetInitialState, SetInputParams, RPC, RECORD, \
    IDLE, PLAY
import socket
import struct
import subprocess
import time
from Tkinter import Button, Frame, Text, Tk, LEFT, W

import midi
import midifile
from StringIO import StringIO

import sys

bindings = '''Key Bindings:
<Space>  Play/Pause.
F8 - save
F5 - record.
F3 - quit.
F2 - load
commands:
    p<n> change program of current channel to n
'''

class Command:
    def __init__(self, name, argDefs, func):
        """
            Args:
                name: [str] the function name
                argDefs: [list<callable(any) -> any>] A list of functions that
                    can appept anything as input and either raise an
                    exception or return the function converted to the
                    appropriate argument type.
                func: [callable(Commands, *args)] Function to be called when
                    the command is invoked.
            """
        self.name = name
        self.argDefs = argDefs
        self.func = func

    def __call__(self, context, *args):
        convertedArgs = []
        for convert, val in zip(self.argDefs, args):
            print 'convert is %r' % convert
            convertedArgs.append(convert(val))
        self.func(context, *convertedArgs)

def setChannel(context, channel):
    """
        Set the current channel.  This is used for subsequent commands and
        will also be sent to the input dispatcher to configure the channel
        that all incoming events are coerced to.

        parms:
            context: [Commands]
            channel: [int]
    """
    context.channel = channel
    req = SetInputParams()
    req.output_channel = channel
    context.comm.sendRPC(set_input_params = req)
    context.out.info('Current channel is %d' % channel)

def setProgram(context, program):
    """
        Set the program for the current channel.

        parms:
            context: [Commands]
            program: [int]
    """

    context.initializers[context.channel] = program
    events = context.getInitializerString()

    # And send it to the dispatcher.  This will cause the program
    # change event to happen immediately and on the first play.
    print 'sending add track'
    setState = SetInitialState()
    setState.dispatcher = 'fluid'
    setState.events = events
    context.comm.sendRPC(set_initial_state = setState)

    context.out.info('Set program to %d' % program)

commands = {
    'ch': Command('ch', [int], setChannel),
    'p': Command('p', [int], setProgram)
}

class Comm:

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.sock.connect(('127.0.0.1', 8193))

    def close(self):
        self.sock.close()

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
        if 'add_track' in kwargs:
            rpc.add_track.CopyFrom(kwargs['add_track'])
        if 'set_initial_state' in kwargs:
            rpc.set_initial_state.add().CopyFrom(kwargs['set_initial_state'])
        if 'set_input_params' in kwargs:
            rpc.set_input_params.CopyFrom(kwargs['set_input_params'])
        parcel = rpc.SerializeToString()
        data = struct.pack('<I', len(parcel)) + parcel
        self.sock.send(data)

class Output:

    def __init__(self, text):
        self.text = text

    def info(self, message):
        self.text.insert('end', str(message) + '\n', 'info')
        self.text.see('end')

    error = info

class Commands:

    def __init__(self, comm):
        self.comm = comm
        self.state = IDLE
        self.out = None

        # The current channel (the target for commands that affect the
        # chennel).  When we do setChannel() (the "ch" command) this is synced
        # to the output channel on the daemon's input dispatcher, but this is
        # not initially the case.
        self.channel = 0

        # A mapping from a channel number to the initializer string for the
        # channel.
        self.initializers = {}

        self.filename = 'noname.mawb'

    def getInitializerString(self):
        """
            Returns the initializer string for the fluid dispatcher,
            constructed from events for all of the channels.
        """
        track = midi.Track()
        for channel, program in self.initializers.iteritems():
            track.add(midi.ProgramChange(0, channel, program))
        return midifile.serializeTrack(track)

    def togglePlay(self, event=None):
        if self.state == IDLE:
            self.comm.sendRPC(change_sequencer_state = PLAY)
            self.state = PLAY
            self.out.info('playing')
        else:
            self.comm.sendRPC(change_sequencer_state = IDLE)
            self.state = IDLE
            self.out.info('paused')
        return 'break'

    def save(self, event):
        self.comm.sendRPC(save_state = self.filename)

    def load(self, event):
        self.comm.sendRPC(load_state = self.filename)

    def restart(self, event):
        self.comm.sendRPC(set_ticks = 0)
        self.out.info('set to 0')
        return 'break'

    def record(self, event):
        # If we're already recording, this switches us to "play" mode.
        if self.state == RECORD:
            self.comm.sendRPC(change_sequencer_state = PLAY)
            self.out.info('playing')
            self.state = PLAY
        else:
            self.comm.sendRPC(set_ticks = 0, change_sequencer_state = RECORD)
            self.state = RECORD
            self.out.info('recording')
        return 'break'

class MyWin(Frame):

    def __init__(self, top, commands):
        Frame.__init__(self, top)
        self.text = Text(self)
        self.text.grid()

        self.buttons = Frame(self)
        self.playBtn = Button(self.buttons, text = '>',
                              command = commands.togglePlay
                              )
        self.playBtn.pack(side = LEFT)
        self.buttons.grid(sticky = W)
        commands.out = Output(self.text)
        self.bindCommands(commands)
        self.commands = commands
        self.grid()

    def eval(self, event):
        cmd = self.text.get('insert linestart', 'insert')
        cmd = cmd.split()

        # We're usurping the "return" key, we need to insert a return
        # character before any command or error output.
        self.text.mark_set('insert', 'insert lineend')
        self.text.insert('insert', '\n')

        try:
            commandObj = commands[cmd[0]]
        except KeyError:
            self.commands.out.info('No such command %s' % cmd[0])
            return 'break'

        try:
            commandObj(self.commands, *cmd[1:])
        except:
            self.commands.out.error(traceback.format_exc())

        return 'break'

    def bindCommands(self, commands):
        top = self.winfo_toplevel()
        top.bind('<F5>', commands.togglePlay)
        top.bind('<F6>', commands.record)
        top.bind('<F7>', commands.restart)
        top.bind('<F8>', commands.load)
        top.bind('<F3>', self.shutdown)
        top.bind('<F2>', commands.save)
        top.bind('<F1>', self.help)

        # Stuff for the console.
        self.text.insert('insert', bindings)
        self.text.bind('<Return>', self.eval)
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
    subprocess.call(['aconnect', '24:0', '129:1'])
    subprocess.call(['jack_connect', 'fluidsynth:l_00', 'system:playback_1'])
    subprocess.call(['jack_connect', 'fluidsynth:r_00', 'system:playback_2'])

    comm = Comm()
    try:
        commands = Commands(comm)
        win = MyWin(Tk(), commands)
        win.mainloop()
    finally:
        comm.close()

run()
