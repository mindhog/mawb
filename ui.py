# Initial command-line user-interface.
# Will turn this into a real UI at some point.

from mawb_pb2 import PBTrack, SetInitialState, SetInputParams, Response, RPC, \
    RECORD, IDLE, PLAY
import socket
import struct
import subprocess
import time
from Tkinter import Button, Entry, Frame, Label, Text, Tk, LEFT, W
from spug.io.proactor import getProactor
import random
import threading
import traceback
from comm import Comm, DaemonManager

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
    context.notify('<<channel-change>>', channel)

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
    context.notify('<<program-change>>', program)

commands = {
    'ch': Command('ch', [int], setChannel),
    'p': Command('p', [int], setProgram)
}

class EventData:
    """
        We can send Tk events from other threads, but we can't store any
        information in them other than a specific set of fields defined by
        Tkinter.  EventData is a global repository that lets us store whatever
        we want and reference it as an integer from the event's 'x' field.
    """

    def __init__(self):
        self.__lock = threading.Lock()
        self.__data = {}

    def store(self, data):
        """
            Stores 'data' (which can be of any type) and returns an integer
            identifier to be stored in an event's 'x' field that can be used
            to look it up.
        """
        with self.__lock:
            key = random.randint(0, 0xFFFF)
            while key in self.__data:
                key = random.randint(0, 0xFFFF)
            self.__data[key] = data
            return key

    def get(self, key):
        """
            Returns the data stored under the specified key, and removes the
            data from the store.  After this, the key may be reused.
        """
        with self.__lock:
            return self.__data.pop(key)

eventData = EventData()

class Output:

    def __init__(self, text):
        self.text = text
        self.text.bind('<<text>>', self.__onText)

    def __onText(self, event):
        text = eventData.get(event.x)
        self.text.insert('end', text + '\n', 'info')
        self.text.see('end')

    def info(self, message):
        # We do this via an event so it will work from any thread.
        self.text.event_generate('<<text>>', x = eventData.store(message))

    error = info

class Commands:

    def __init__(self, comm):
        self.comm = comm
        self.state = IDLE
        self.out = None
        self.window = None

        # The current channel (the target for commands that affect the
        # chennel).  When we do setChannel() (the "ch" command) this is synced
        # to the output channel on the daemon's input dispatcher, but this is
        # not initially the case.
        self.channel = 0

        # A mapping from a channel number to the initializer string for the
        # channel.
        self.initializers = {}

        self.filename = 'noname.mawb'

    def notify(self, eventName, param):
        """Sends a virtual event to the user interface."""
        self.window.event_generate(eventName, x = eventData.store(param))

    def getInitializerString(self):
        """
            Returns the initializer string for the fluid dispatcher,
            constructed from events for all of the channels.
        """
        track = midi.Track()
        for channel, program in self.initializers.items():
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

    def __restoreInitializers(self, project):
        self.initializers = {}
        for disp in project.dispatchers:
            if disp.name == 'fluid':
                track = disp.initial_state
                break
        else:
            # No initializers.
            return

        # Parse the program change events out of the track.
        track = midifile.readTrack(track, 'track-name')
        for event in track:
            if isinstance(event, midi.ProgramChange):
                print 'storing program change %d %d' % (event.channel,
                                                        event.program)
                self.initializers[event.channel] = event.program

    def load(self, event):

        def loaded(resp):
            self.__restoreInitializers(resp.project)
            self.out.info('loaded project')

        self.comm.sendRPC(load_state = self.filename,
                          callback = loaded
                          )

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

def setROField(field, value):
    """
        Helper function to set the value of a read-only field.

        parms:
            field: [Tkinter.Entry]
            value: [str]
    """
    field.configure(state = 'normal')
    field.delete(0, 'end')
    field.insert(0, value)
    field.configure(state = 'readonly')


def makeROEntry(parent, row, column, label, initVal):
    lbl = Label(parent, text = label)
    lbl.grid(row = row, column = column)
    entry = Entry(parent)
    entry.grid(row = row, column = column + 1)
    entry['readonly'] = 'gray10'
    entry.insert(0, initVal)
    entry['state'] = 'readonly'
    return lbl, entry

def getProgramName(program):
    """
        Returns the string program name for the given program number.
    """
    return '%d %s' % (program, midi.programs[program])

class MyWin(Frame):

    def __init__(self, top, commands):
        Frame.__init__(self, top)
        self.text = Text(self)
        self.text.grid()

        commands.window = self
        self.bind('<<channel-change>>', self.__onChannelChange)
        self.bind('<<program-change>>', self.__onProgramChange)

        self.buttons = Frame(self)
        self.playBtn = Button(self.buttons, text = '>',
                              command = commands.togglePlay
                              )
        self.playBtn.pack(side = LEFT)
        self.buttons.grid(sticky = W)

        self.status = Frame(self)
        self.status.channelLbl, self.status.channelTxt = \
            makeROEntry(self.status, 0, 0, 'Channel:', '0')
        self.status.programLbl, self.status.programTxt = \
            makeROEntry(self.status, 0, 2, 'Program:', getProgramName(0))
        self.status.grid(sticky = W)

        commands.out = Output(self.text)
        self.bindCommands(commands)
        self.commands = commands
        self.grid()

    def __setProgramField(self, program):
        setROField(self.status.programTxt, getProgramName(program))

    def __onChannelChange(self, event):
        channel = eventData.get(event.x)
        setROField(self.status.channelTxt, str(channel))
        self.__setProgramField(self.commands.initializers.get(channel, 0))

    def __onProgramChange(self, event):
        self.__setProgramField(eventData.get(event.x))

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

def run():
    daemon = DaemonManager()
    daemon.start()


    # Stuff that should clearly be elsewhere.
    subprocess.call(['aconnect', '130:0', '129:1'])
    subprocess.call(['aconnect', '24:0', '129:1'])
    subprocess.call(['jack_connect', 'fluidsynth:l_00', 'system:playback_1'])
    subprocess.call(['jack_connect', 'fluidsynth:r_00', 'system:playback_2'])

    comm = Comm()

    # Start the proactor thread.  We do this after Comm() has been created so
    # there are connections to manage, otherwise the proactor will just
    # immediately terminate.
    proactorThread = threading.Thread(target = getProactor().run)
    proactorThread.start()

    try:
        commands = Commands(comm)
        win = MyWin(Tk(), commands)
        win.mainloop()
    finally:
        comm.close()
        proactorThread.join()

run()
