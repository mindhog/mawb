
import abc
from enum import Enum
from heapq import merge
from midi import Event
from modes import MidiState
from tkinter import Button, Entry, Frame, Label, Listbox, Menu, Menubutton, \
    Text, Tk, Toplevel, Widget, BOTH, LEFT, NORMAL, NSEW, RAISED, W
from typing import Callable, List
from awb_client import ACTIVE, NONEMPTY, RECORD, STICKY
from awb_client import offsetEventTimes, AWBClient, CallableEvent, ACTIVE, \
    NONEMPTY, RECORD, STICKY
from commands import Program, ProgramCommands, ScriptInterpreter
import time
import traceback

class Channel(Frame):
    """These are the "classic channels", audio config and recording.

    Stuff a channel tracks:
    -   The track number
    -   Recording
    -   Active
    -   Muted
    -   Sticky
    -   Non-empty
    """

    def __init__(self, parent, trackNumber):
        Frame.__init__(self, parent, relief = RAISED, borderwidth = 3,
                       background = 'black')
        self.channel = trackNumber

        self.record = False
        self.nonEmpty = False
        self.active = False
        self.sticky = False

        self.label = Label(self)
        self.label.pack()
        self.__updateStatus()
        self.configure(relief = RAISED)

    def __updateStatus(self):

        # First and last characters are brackets for the active track.
        # Second character is 'R' for recording, 'P' for playing and ' ' for
        # empty.  Third character is '*' for sticky, ' ' if not.
        self.label.configure(text = '%d: %s%s%s%s' % (
                                self.channel,
                                self.active and '[' or ' ',
                                self.record and 'R' or
                                self.nonEmpty and 'P' or
                                ' ',
                                self.sticky and '*' or ' ',
                                self.active and ']' or ' '
                             ))

    def changeStatus(self, status):
        self.nonEmpty = status & NONEMPTY
        self.record = status & RECORD
        self.sticky = status & STICKY
        self.active = status & ACTIVE
        print('changing status of %d, nonempty = %s, record = %s, '
              'sticky = %s, active = %s' % (self.channel, self.nonEmpty,
                                            self.record, self.sticky,
                                            self.active))
        self.__updateStatus()

class SelectionClient(abc.ABC):
    """Interface for a window that initiates a TextSelect popup.

    Contains callbacks for when the popup completes.
    """

    @abc.abstractmethod
    def selected(self, selection):
        """Called when an item is selected."""

    @abc.abstractmethod
    def aborted(self):
        """Called when the text selection is aborted (user has pressed
        "Escape")
        """

class ProgramChanger(Frame, SelectionClient):
    """Widget to specify a bank/program change event (a MidiState object)."""

    def __init__(self, parent: 'Widget', client: 'AWBClient',
                 model: MidiState,
                 onCommit: Callable[[MidiState], None],
                 **kwargs):
        super(ProgramChanger, self).__init__(parent, **kwargs)

        self.__parent = parent
        self.__awb = client
        self.__orgModel = model
        self.__newModel = model.clone()
        self.__onCommit = onCommit

        lbl = Label(self, text = 'Port:')
        lbl.grid(row = 0, column = 0)
        self.__port = Button(self, text=model.portName,
                             command=self.__selectPort
                             )
        self.__port.grid(row = 0, column = 1)

        def validateInt(val):
            if val == '':
                # Allow empty string so that we can comfortably edit this
                # field.
                return True
            try:
                val = int(val)
                return True
            except ValueError:
                return False

        validateIntCB = self.register(validateInt)

        lbl = Label(self, text='Bank:')
        lbl.grid(row = 1, column = 0)
        self.__bank = Entry(self, validate='key',
                            validatecommand=(validateIntCB, '%P')
                            )
        self.__bank.insert(0, str(model.bank))
        self.__bank.grid(row = 1, column = 1)
        lbl = Label(self, text='Program:')
        lbl.grid(row = 2, column = 0)
        self.__program = Entry(self, validate='key',
                               validatecommand=(validateIntCB, '%P')
                               )
        self.__program.insert(0, str(model.program))
        self.__program.grid(row=2, column=1)

        btn = Button(self, text='-', command=self.__programDec)
        btn.grid(row=2, column=2)
        btn = Button(self, text='+', command=self.__programInc)
        btn.grid(row=2, column=3)

        btnRow = Frame(self)
        btn = Button(btnRow, text='Save', command=self.__save)
        btn.pack(side=LEFT)
        btn = Button(btnRow, text='Cancel', command=self.__cancel)
        btnRow.grid(row=3, column=0, columnspan=4)

    def __save(self, *event):
        self.__newModel.bank = self.__getIntValue(self.__bank)
        self.__newModel.program = self.__getIntValue(self.__program)
        self.__onCommit(self.__newModel)
        # TODO: We destroy the parent, making the assumption that it is a
        # toplevel, but this class was structured to be usable as an inline
        # window.  We should probably let the parent decide how to destroy it.
        self.__parent.destroy()

    def __cancel(self, *event):
        self.__parent.destroy()

    def selected(self, selection):
        self.__port.configure(text = selection)
        self.__newModel.portName = selection

    def aborted(self):
        pass

    def __selectPort(self, *event):
        selector = TextSelect(self, self.__port, _getPorts(self.__awb))

    @staticmethod
    def __getIntValue(control: Entry):
        result = control.get()
        return 0 if result == '' else int(result)

    def __getProgramValue(self):
        return self.__getIntValue(self.__program)

    def __getBankValue(self):
        return self.__getIntValue(self.__bank)

    def __fillNewModel(self):
        self.__newModel.bank = self.__getBankValue()
        self.__newModel.program = self.__getProgramValue()

    def __setProgramValue(self, val: int):
        self.__program.delete(0, 'end')
        self.__program.insert(0, str(val))

    def __changeProgram(self):
        """Change the program of the port's midi device to the current program.
        """
        self.__fillNewModel()
        if self.__newModel.portName != 'port':
            self.__newModel.activate(self.__awb)

    def __programDec(self):
        val = self.__getProgramValue() - 1
        if val == -1:
            val = 127
        self.__setProgramValue(val)
        self.__changeProgram()

    def __programInc(self):
        val = self.__getProgramValue() + 1
        if val == 128:
            val = 0
        self.__setProgramValue(val)
        self.__changeProgram()

class ConfigPresetEditor(Toplevel):

    # TODO: follow the mutation pattern used by ProgramChanger: pass in the
    # original object and a commit method.
    def __init__(self, client: 'AWBClient', preset: 'StateVec'):
        super(ConfigPresetEditor, self).__init__()

        self.__preset = preset

        self.__list = Listbox(self)
        self.__list.grid(columnspan=2)
        for attr in dir(self.__preset):
            if attr.startswith('prog:'):
                self.__list.insert('end', attr)

        buttonPnl = Frame(self)
        button = Button(buttonPnl, text='New Program',
                        command=self.__newProgram
                        )
        button.pack(side=LEFT)
        button = Button(buttonPnl, text = 'Edit', command=self.__edit)
        button.pack(side=LEFT)
        button = Button(buttonPnl, text='Delete', command=self.__delete)
        button.pack(side=LEFT)
        buttonPnl.grid(columnspan = 2)
        self.__awb = client

    def __newProgram(self):
        def addProgram(state: MidiState):
            # store the preset. TODO: add channel to the name.
            name = 'prog:%s' % state.portName
            setattr(self.__preset, name, state)
            self.__list.insert('end', name)
            print(dir(self.__preset))
        c = ProgramChanger(Toplevel(), self.__awb, MidiState('port', 0, 0),
                           addProgram
                           )
        c.grid(sticky=NSEW)

    def __edit(self):
        selIndex = self.__list.curselection()
        if len(selIndex) != 1:
            # TODO: show error
            return
        selIndex = selIndex[0]
        oldName = self.__list.get(selIndex)

        def updateProgram(state: MidiState):
            self.__list.delete(selIndex)
            name = 'prog:%s' % state.portName
            delattr(self.__preset, oldName)
            setattr(self.__preset, name, state)
            self.__list.insert(selIndex, name)
        c = ProgramChanger(Toplevel(), self.__awb,
                           getattr(self.__preset, oldName),
                           updateProgram
                           )
        c.grid(sticky=NSEW)

    def __delete(self):
        selIndex = self.__list.curselection()
        if len(selIndex) != 1:
            # TODO: show error
            return
        selIndex = selIndex[0]

        name = self.__list.get(selIndex)
        self.__list.delete(selIndex)
        del self.__items[selIndex]
        delattr(self.__preset, name)

class ConfigPreset(Button):
    """The button that selects a config preset.

    Can also be right-clicked to edit the configuration.
    """

    def __init__(self, parent: 'Widget', client: 'AWBClient', text: str,
                 index: int,
                 **kwargs
                 ):
        """
        Args:
            text: Name to display on the button.
            index: index of the config preset button in the ConfigPresetRow.
        """
        super(ConfigPreset, self).__init__(parent, text=text)
        self.bind('<Button-3>', self.__menu)
        self.__awb = client
        self.__index = index

        # Create a pop-up menu.
        self.__popup = Menu(self, tearoff = False)
        self.__popup.add_command(label = 'Configure',
                                 command = self.__configure
                                 )

    def activate(self, active: bool):
        """Activate/deactivate the button based on the value of 'active'."""
        if active:
            self.configure(background = 'DarkRed')
        else:
            self.configure(background = 'DarkGray')

    def __menu(self, event):
        self.__popup.tk_popup(event.x_root, event.y_root, 0)

    def __configure(self):
        """Starts the configuration window."""
        config = ConfigPresetEditor(self.__awb, self.__awb.voices[self.__index])

class ConfigPresetRow(Frame):
    """A row of config preset buttons."""

    def __init__(self, parent: 'Widget', client: 'AWBClient', count: int,
                 **kwargs
                 ):
        super(ConfigPresetRow, self).__init__(**kwargs)
        assert count > 0 # We assume __current is valid below.
        self.__buttons = []
        self.__current = 0
        self.__client = client
        for i in range(count):
            button = ConfigPreset(self, client, str(i), i)
            button.pack(side = LEFT)
            self.__buttons.append(button)

            # Button press callback.
            def pressed(index=i, *args):
                self.__activate(index)
                self.__client.activate(index)

            button.configure(command = pressed)
            client.addChannelSubscriber(i, self.__statusCallback)

    def __activate(self, index):
        self.__buttons[self.__current].activate(False)
        self.__current = index
        self.__buttons[index].activate(True)

    def __statusCallback(self, channel: int, modes: int):
        if modes & ACTIVE:
            self.__activate(channel)

class Counter:

    def __init__(self):
        self.val = 0

    def __call__(self):
        result = self.val
        self.val += 1
        return result

class EventMultiplexer:
    """Sends an event to multiple handlers."""

    def __init__(self, *handlers):
        self.handlers = handlers

    def __call__(self):
        for handler in self.handlers:
            handler()

class RecordingInfo:
    """Tracks information on a recorded midi-macro."""

    def __init__(self, name, events):
        self.name = name
        self.events = events

    def __str__(self):
        return self.name

class EventRecorder:
    def __init__(self, name: str):
        self.name = name
        self.events = []

        # __startTime is the time of the first event (seconds since the epoch).
        self.__startTime : float = 0

    def __call__(self, client: AWBClient, event: Event) -> bool:
        if self.__startTime:
            event.time = client.getTicks(time.time() - self.__startTime)
        else:
            self.__startTime = time.time()
            event.time = 0
        self.events.append(event)
        return False

    def getRecordingInfo(self) -> RecordingInfo:
        return RecordingInfo(self.name, self.events)

class LRState(Enum):
    RECORD = 0
    PLAYING = 1
    IDLE = 2

class LoopRegister:
    """Stores a set of events as a loop.

    The loop register has three states: recording, playing and idle.  It
    transitions from recording to playing and then from playing to idle and
    then from idle to playing, which works well for a single button control.
    """

    def __init__(self, client: AWBClient):
        self.__client = client
        self.__events = []
        self.__state = LRState.RECORD
        self.__start : Optional[int] = None

    def nextState(self):
        def reschedule(client: AWBClient):
            if self.__state == LRState.PLAYING:
                self.__client.scheduleMidiEvents(self.__events)

        if self.__state == LRState.RECORD:
            t = self.__client.getTicks() - self.__start
            self.__events.append(CallableEvent(t, reschedule))
            self.__state = LRState.PLAYING
            reschedule(self.__events)
        elif self.__state == LRState.PLAYING:
            self.__state = LRState.IDLE
        elif self.__state == LRState.IDLE:
            self.__state = LRState.PLAYING
            reschedule(self.__events)

    def addEvents(self, events):
        # Ignore events added when not recording.
        if not self.__state == LRState.RECORD:
            return

        # Record the start time if there is none, otherwise use it to
        # calculate the loop-relative time.
        if self.__start is None:
            self.__start = self.__client.getTicks()
            t = 0
        else:
            t = self.__client.getTicks() - self.__start
        self.__events = list(merge(offsetEventTimes(events, t),
                                   self.__events,
                                   key=lambda e: e.time
                                   )
                             )

    @property
    def state(self):
        return self.__state


class MidiRegisters(Toplevel):
    """Window containing and controlling a set of midi registers.

    This has to be a toplevel so it can have toplevel bindings.
    """

    STATUS_TEXT = 'Hit unbound key to record'

    def __init__(self, client: AWBClient):
        super().__init__()
        self.client = client
        self.__recorder : Optional[EventRecorder] = None
        self.__registers : Dict[str, RecordingInfo] = {}
        self.__loop : Optional[LoopRegister] = None
        self.frame = Frame(self)
        self.status = Label(self.frame, text=self.STATUS_TEXT)
        self.status.pack()
        self.list = Listbox(self.frame)
        self.list.pack(expand=True, fill=BOTH)

        self.__loopStat = Label(self.frame, text='Loop 1: EMPTY')
        self.__loopStat.pack()

        lower_frame = Frame(self)
        #self.entry = Entry(lower_frame)
        #record = Button(lower_frame, text='Record', command=self.__add)
        self.frame.grid(row = 0, column = 0, sticky=NSEW)
        self.bind('<KeyPress>', self.__keypress)


    def __keypress(self, event):
        print(f'keysym is {event.keysym}')

        # Check for special keys.
        if len(event.keysym) > 1:
            if event.keysym == 'Delete':
                sel = self.list.curselection()
                if sel:
                    key = self.list.get(sel[0])
                    del self.__registers[key]
                    self.list.delete(sel[0])
            elif event.keysym == 'F1':
                if self.__loop:
                    self.__loop.nextState()
                    self.__loopStat.configure(
                        text=f'Loop 1: {self.__loop.state}')
                else:
                    self.__loop = LoopRegister(self.client)
            return

        # play an existing register.
        try:
            events = self.__registers[event.keysym].events
            self.client.scheduleMidiEvents(events)
            if self.__loop:
                self.__loop.addEvents(events)
            return
        except KeyError:
            pass

        # If the key we're recording was pressed again, end record.
        if self.__recorder and self.__recorder.name == event.keysym:
            trackInfo = self.__recorder.getRecordingInfo()
            self.client.inputProcessors.remove(self.__recorder)
            self.__recorder = None
            self.list.insert(len(self.__registers), str(trackInfo))
            self.__registers[trackInfo.name] = trackInfo
            self.status.configure(text=self.STATUS_TEXT)

        # If we're not recording, start recording on that key.
        elif not self.__recorder:
            self.__recorder = EventRecorder(event.keysym)
            self.status.configure(
                text=f'Recording on {event.keysym}: press again to finish'
            )
            self.client.inputProcessors.append(self.__recorder)

class MainWin(Tk):

    def __init__(self, client):
        Tk.__init__(self)
        self.title('MAWB')
        self.client = client
        self.programPanel = ProgramPanel(self, client)
        self.programPanel.grid(row = 0, column = 0, sticky = NSEW)

        self.frame = Frame(self)
        self.frame.grid(row = 0, column = 0, sticky = NSEW)
        nextRow = Counter()

        # Create the menu.
        menubar = Frame(self.frame)
        addButton = Menubutton(menubar, text = 'File')
        addButton.pack()
        menubar.grid(row = nextRow(), column = 0, sticky = W)
        fileMenu = Menu(addButton, tearoff = False)
        fileMenu.add_command(label='Save', command=self.__save)
        fileMenu.add_command(label='Load', command=self.__load)
        addButton['menu'] = fileMenu

        # Create the program panel.
        self.program = ProgramWidget(self.frame, client)
        self.program.grid(row = nextRow(), column = 0, columnspan = 2,
                          sticky = W)

        fileMenu.add_command(label='Plugins', command=self.__plugins)
        fileMenu.add_command(label='Midi Registers', command=self.__registers)
        addButton['menu'] = fileMenu

        label = Label(self.frame, text = 'AWB')
        label.grid(row = nextRow(), column = 0)

        self.recordMode = Button(self.frame, text = 'P',
                                 command = lambda e: self.toggleRecord())
        modeRow = nextRow()
        self.recordMode.grid(row = modeRow, column = 0, sticky = W)
        self.status = Label(self.frame, text = 'Idle')
        self.status.grid(row = modeRow, column = 1)

        self.channels = []
        self.channelFrame = Frame(self.frame)
        self.channelFrame.grid(row = nextRow(), columnspan = 2)

        self.bind('q', self.terminate)
        self.bind('f', self.foo)

        self.bind('r', self.toggleRecord)
        self.bind('k', self.toggleSticky)
        self.bind('.', self.nextSection)
        self.bind(',', self.prevSection)
        self.bind('<space>', self.togglePause)
        self.bind('K', self.clearAllState)
        self.protocol('WM_DELETE_WINDOW', self.destroy)

        # F1 key brings the main panel to the foreground
        self.bind('<F1>', lambda evt: self.frame.tkraise())
        # F2 brings the Program panel to the foreground.
        self.bind('<F2>', lambda evt: self.programPanel.tkraise())

        for i in range(0, 8):

            # Bind number key.
            self.bind(str(i),
                      lambda evt, channel = i: self.toggleChannel(channel)
                      )

            # Create channel
            channel = Channel(self.channelFrame, i)
            self.channels.append(channel)
            channel.pack(side = LEFT)

            client.addChannelSubscriber(
                i,
                lambda ch, status, channel = channel:
                    channel.changeStatus(status)
            )

        client.onProgramChange = EventMultiplexer(
            self.program.programChanged,
            self.programPanel.programChanged
        )

    def __save(self, *args):
        self.client.writeTo(open('noname.mawb', 'wb'))

    def __load(self, *args):
        # TODO: display a file selector.
        self.client.readFrom(open('noname.mawb', 'rb'))

    def __plugins(self, *args):
        top = Toplevel()
        plugins = Plugins(top, self.client)
        plugins.grid()

    def __registers(self, *args):
        top = MidiRegisters(self.client)

    def foo(self, event):
        print('got foo')

    def terminate(self, event):
        self.destroy()

    def toggleRecord(self, event):
        self.client.recordEnabled = not self.client.recordEnabled
        self.recordMode.configure(text = self.client.recordEnabled and 'R' or
                                  'P'
                                  )

    def togglePause(self, event):
        self.client.togglePause()
        if self.client.paused:
            self.status.configure(text = 'Paused')
        else:
            self.status.configure(text = 'Playing')

    def clearAllState(self, event):
        self.client.clearAllState()
        self.status.configure(text = 'Idle')
        for channel in self.channels:
            channel.changeStatus(0)

    def toggleChannel(self, channel):
        # using "channel" as program
        self.client.activate(channel)
        if self.client.recording.get(channel):
            self.client.endRecord(channel)
        elif self.client.recordEnabled:
            self.client.startRecord(channel)
        self.status.configure(text = 'Recording on %s' % channel)

    def __getActiveChannel(self):
        # Move this to awb_client
        for i, ch in enumerate(self.channels):
            if ch.active:
                return i

    def toggleSticky(self, event):
        channel = self.__getActiveChannel()
        self.client.toggleChannelSticky(channel)

    def nextSection(self, event):
        self.client.nextOrNewSection()

    def prevSection(self, event):
        self.client.prevSection()

    def add(self, widget: 'Widget'):
        """Add a widget to the front panel of the window."""
        widget.grid(columnspan = 2, sticky = NSEW)

class ProgramWidget(Frame):
    """Widget that displays the main application "program" (script) panel."""

    def __init__(self, parent, client):
        super(ProgramWidget, self).__init__(parent)
        self.client = client

        self.programLabel = Label(self, text = 'Program:')
        self.programLabel.grid(row = 0, column = 0)
        self.programEntry = Entry(self, text = 'Program name',
                                  state = 'readonly')
        self.programEntry.grid(row = 0, column = 1)
        self.buttonPanel = Frame(self)
        self.buttonPanel.grid(row = 1, column = 0, columnspan = 2, sticky = W)
        self.newButton = Button(self.buttonPanel, text='New',
                                command = self.newProgram)
        self.newButton.pack(side = LEFT)

    def programChanged(self):
        self.__setProgramText(str(self.client.state))

    def __setProgramText(self, text):
        self.programEntry.configure(state = NORMAL)
        self.programEntry.delete(0)
        self.programEntry.insert(0, text)
        self.programEntry.configure(state = 'readonly')

    def newProgram(self):
        self.client.makeNewProgram()

class TextSelect(Frame):

    def __init__(self, client, anchor, items, destroyAnchor=False):
        """
        Args:
            client: [SelectionClient] The window that text is returned to.
            anchor: A window that the text selection popup is created
                relative to.
            items: [str], items to display in the listbox.
            destroyAnchor: [bool] if true, destroy the anchor after
                positioning the window.
        """
        self.top = Toplevel()
        self.anchor = anchor
        self.top.overrideredirect(1)
        self.top.wm_geometry('+%s+%s' % (anchor.winfo_rootx() + anchor.winfo_x(),
                                         anchor.winfo_rooty() + anchor.winfo_y()
                                         )
                             )
        super(TextSelect, self).__init__(self.top)
        self.entry = Entry(self)
        self.client = client
        self.items = items
        self.place(x = 0.5, y = 0.5, height = 100, width = 100)
        self.entry.bind('<Return>', self.close)
        self.entry.bind('<KeyPress>', self.filter)
        self.entry.bind('<Escape>', self.abort)
        self.entry.bind('<Up>', self.up)
        self.entry.bind('<Down>', self.down)
        self.entry.pack()

        # Create the list of items.
        self.list = Listbox(self)
        for item in self.items:
            self.list.insert('end', item)
        self.list.pack()
        self.grid()
        self.entry.focus()

        # Reposition the select button against the anchor.  We defer this
        # until after idle so that the anchor has a chance to get rendered.
        def reposition(*args):
            self.top.wm_geometry('+%s+%s' % (
                anchor.winfo_rootx(),
                anchor.winfo_rooty())
            )
            if destroyAnchor:
                anchor.destroy()
        self.after_idle(reposition)

    def close(self, event):
        sel = self.list.curselection()
        if sel:
            item = self.list.get(sel[0])
        else:
            item = self.entry.get()

        # Note that the order of this appears to be significant: destroying
        # before selecting leaves the focus in a weird state.
        self.client.selected(item)
        self.top.destroy()
        return 'braek'

    def abort(self, event):
        self.top.destroy()
        self.client.aborted()
        return 'break'

    def up(self, event):
        sel = self.list.curselection()
        if not sel:
            self.list.selection_set(0)
            return 'break'
        sel = sel[0]

        print('sel is %s size is %s' % (sel, self.list.size()))
        if sel > 0:
            print('setting selection to %s' % sel)
            self.list.selection_clear(sel)
            self.list.selection_set(sel - 1)
            self.list.see(sel)
        return 'break'

    def down(self, event):
        sel = self.list.curselection()
        if not sel:
            self.list.selection_set(0)
            return 'break'
        sel = sel[0]

        print('sel is %s size is %s' % (sel, self.list.size()))
        if sel < self.list.size() - 1:
            print('setting selection to %s' % (sel + 1))
            self.list.selection_clear(sel)
            self.list.selection_set(sel + 1)
            self.list.see(sel)
        return 'break'

    def filter(self, event):
        """Filter the listbox based on the contents of the entryfield."""
        # first add the character to the entry.
        currentText = self.entry.get()
        print(event.keysym)
        if event.keysym == 'BackSpace':
            # Handle backspace specially.
            if currentText:
                currentText = currentText[:-1]
                self.entry.delete(0, 'end')
                self.entry.insert(0, currentText)
            else:
                return 'break'
        else:
            # Assume normal character. Insert it.
            self.entry.insert('insert', event.char)
            currentText += event.char

        self.list.delete(0, 'end')
        pattern = currentText.upper()
        for item in self.items:
            if pattern in item.upper():
                self.list.insert('end', item)

        return 'break'

def _getPorts(client: 'AWBClient') -> List[str]:
    result = []
    for port in client.seq.iterPortInfos():
        result.append(port.fullName)
    return result

class ProgramPanel(Frame):
    """Lets you configure the program."""

    def __init__(self, parent, client):
        super(ProgramPanel, self).__init__()
        self.client = client
        self.text = Text(self)
        self.text.grid(row = 0, column = 0, sticky = NSEW)

        self.text.bind('<Tab>', self.showCompletions)
        self.text.bind('<Return>', self.eval)
        self.text.focus()

        self.info = Label(self)
        self.info.grid(row = 1, column = 0, sticky = NSEW)

        # Do a programChanged to set the current program.
        self.programChanged()

    def selected(self, item):
        self.__insertWord(item)
        self.text.focus()

    def aborted(self):
        self.text.focus()

    def __insertWord(self, word):
        if ' ' in word:
            self.text.insert('insert', ' "%s"' % word)
        else:
            self.text.insert('insert', ' ' + word)

    def programChanged(self):
        """Handler for program change events."""
        program = self.client.state
        self.text.delete('1.0', 'end')
        if isinstance(program, Program):
            print('text is %r' % program.text)
            self.text.insert('1.0', program.text)
            print('setting interp')
            self.interp = ScriptInterpreter(
                ProgramCommands(self.client, program).dict,
            )
        else:
            self.text.insert('1.0', '# uneditable program type\n')

    def showCompletions(self, event):
        selector = None
        anchor = None
        anchor = Frame(self.text)
        self.text.window_create('insert', window=anchor)
        selector = TextSelect(self, anchor, _getPorts(self.__client),
                              destroyAnchor = True)
        return 'break'

    def eval(self, event):
        contents = self.text.get('1.0', 'end') + '\n'
        try:
            self.interp.feed(contents)
            self.client.state.activate(self.client, self.client.state)
            self.setInfo('ok')
        except Exception as ex:
            traceback.print_exc()
            self.setInfo(str(ex))

    def setInfo(self, infoText: str):
        self.info.configure(text = infoText)

#class PluginFrame(Frame):
#    """Wraps and manages a plugin config UI."""
#
#    def __init__(self,

class Plugins(Frame):
    """The plugins manager window.

    Lets you add and remove plugins.
    """

    def __init__(self, parent: 'Widget', client: 'AWBClient', **kwargs):
        super(Plugins, self).__init__(parent)

        self.__client = client

        # Listboxes of current and available plugins.
        label = Label(self, text='Installed')
        label.grid(row=0, column=0)
        label = Label(self, text='Available')
        label.grid(row=0, column=1)
        self.__currentList = Listbox(self)
        self.__currentList.grid(row=1, column=0, sticky=NSEW)
        self.__availList = Listbox(self)
        self.__availList.grid(row=1, column=1, sticky=NSEW)

        buttons = Frame(self)
        button = Button(buttons, text='Add', command=self.__add)
        button.pack(side=LEFT)
        button = Button(buttons, text='Delete')
        button.pack(side=LEFT)
        button = Button(buttons, text='Edit')
        button.pack(side=LEFT)
        buttons.grid(row=2, column=0, columnspan=2, sticky=W)

        # Populate the list from the client.
        for plugin in client.listPlugins():
            self.__availList.insert('end', plugin)

        # Populate the list of loaded plugins from the client.
        for plugin in client.getPlugins():
            self.__currentList.insert('end', str(plugin))

    def __add(self, *args):
        sel = self.__availList.curselection()
        if len(sel) != 1:
            return
        plugin = self.__client.loadPlugin(self.__availList.get(sel[0]))
        ui = plugin.getUI()
        if ui:
            # TODO: replace Toplevel with PluginFrame above.  When the frame
            # is dismissed, we'll want to add the plugin to our list like
            # below.
            ui.create(Toplevel())
        else:
            self.__currentList.insert('end', str(plugin))


def runTkUi(client):
    mainwin = MainWin(client)
    mainwin.mainloop()

if __name__ == '__main__':
    runTkUi(None)


