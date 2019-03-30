
import abc
from tkinter import Button, Entry, Frame, Label, Listbox, Menu, Menubutton, \
    Text, Tk, Toplevel, BOTH, LEFT, NORMAL, NSEW, RAISED, W
from awb_client import ACTIVE, NONEMPTY, RECORD, STICKY

class Channel(Frame):
    """

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

class Counter:

    def __init__(self):
        self.val = 0

    def __call__(self):
        result = self.val
        self.val += 1
        return result

class MainWin(Tk):

    def __init__(self, client):
        Tk.__init__(self)
        self.client = client
        self.programPanel = ProgramPanel(client)
        self.programPanel.grid(row = 0, column = 0, sticky = NSEW)

        self.frame = Frame(self)
        self.frame.grid(row = 0, column = 0, sticky = NSEW)
        nextRow = Counter()

        # Create the menu.
        menu = Frame(self.frame)
        addButton = Menubutton(menu, text = 'Add')
        addButton.pack()
        menu.grid(row = nextRow(), column = 0, sticky = W)

        # Create the program panel.
        self.program = ProgramWidget(self.frame, client)
        self.program.grid(row = nextRow(), column = 0, columnspan = 2,
                          sticky = W)

        label = Label(self.frame, text = 'AWB')
        label.grid(row = nextRow(), column = 0)

        self.recordMode = Button(self.frame, text = 'P',
                                 command = self.toggleRecord)
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

        self.bind('<F1>', lambda evt: self.frame.tkraise())
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

class ProgramWidget(Frame):

    def __init__(self, parent, client):
        super(ProgramWidget, self).__init__(parent)
        self.client = client
        self.client.onProgramChange = self.programChanged

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

class ProgramPanel(Frame):
    """Lets you configure the program."""

    def __init__(self, client):
        super(ProgramPanel, self).__init__()
        self.client = client
        self.text = Text(self)
        self.text.grid(row = 0, column = 0, sticky = NSEW)

        self.text.bind('<Tab>', self.showCompletions)
        self.text.bind('<Return>', self.eval)
        self.text.focus()

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

    def __getPorts(self):
        result = []
        for port in self.client.seq.iterPortInfos():
            result.append(port.fullName)
        return result

    def showCompletions(self, event):
        selector = None
        anchor = None
        anchor = Frame(self.text)
        self.text.window_create('insert', window=anchor)
        selector = TextSelect(self, anchor, self.__getPorts(),
                              destroyAnchor = True)
        return 'break'

def runTkUi(client):
    mainwin = MainWin(client)
    mainwin.mainloop()

if __name__ == '__main__':
    runTkUi(None)


