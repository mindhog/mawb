
from Tkinter import Button, Frame, Label, Tk, LEFT, RAISED
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
        print 'changing status of %d, nonempty = %s, record = %s, ' \
            'sticky = %s, active = %s' % (self.channel, self.nonEmpty,
                                          self.record, self.sticky,
                                          self.active)
        self.__updateStatus()

class MainWin(Tk):

    def __init__(self, client):
        Tk.__init__(self)
        self.client = client
        self.frame = Frame(self)
        self.frame.pack(side = LEFT)
        label = Label(self.frame, text = 'AWB')
        label.grid(row = 0, column = 0)

        self.recordMode = Button(self.frame, text = 'P',
                                 command = self.toggleRecord)
        self.recordMode.grid(row = 1, column = 0)
        self.status = Label(self.frame, text = 'Idle')
        self.status.grid(row = 1, column = 1)

        self.channels = []
        self.channelFrame = Frame(self.frame)
        self.channelFrame.grid(row = 2, columnspan = 2)

        self.bind('q', self.terminate)
        self.bind('f', self.foo)

        self.bind('r', self.toggleRecord)

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
        print 'got foo'

    def terminate(self, event):
        self.destroy()

    def toggleRecord(self, event):
        self.client.recordEnabled = not self.client.recordEnabled
        self.recordMode.configure(text = self.client.recordEnabled and 'R' or
                                  'P'
                                  )

    def toggleChannel(self, channel):
        # using "channel" as program
        self.client.activate(channel)
        if self.client.recording.get(channel):
            self.client.endRecord(channel)
        elif self.client.recordEnabled:
            self.client.startRecord(channel)
        self.status.configure(text = 'Recording on %s' % channel)


def runTkUi(client):
    mainwin = MainWin(client)
    mainwin.mainloop()

if __name__ == '__main__':
    runTkUi(None)

