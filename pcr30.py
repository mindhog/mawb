"""PCR-30 specialization module.

Contains my special controls for the Edirol PCR-30.
"""

from modes import SubState
from midi import ChannelEvent, SysContinue, SysStart, SysStop

class DestPort(SubState):
    """On activation, applies a port to the 'dest' attribute of its target."""

    def __init__(self, target, port, channel = 0):
        self.target = target
        self.port = port
        self.channel = channel

    def activate(self):
        self.target.channel = self.channel
        self.target.dest = self.port

    def __eq__(self, other):
        return self is other or \
               (issubclass(other.__class__, self.__class__) and
                self.target == other.target and
                self.port == other.port)

class Port(object):
    """Bundles together the port and its sequencer.

    Translates "sendEvent()" into "self.seq.sendEvent(port)".
    """
    def __init__(self, seq, port):
        self.seq = seq
        self.dest = port
        self.channel = 0

    def sendEvent(self, event):
        if isinstance(event, ChannelEvent):
            if event.channel != self.channel:
                event._amidi_raw = None
                event.channel = self.channel
        else:
            print 'xxx not a channel event'
        self.seq.sendEvent(event, self.dest)

class PCR30(object):

    def __init__(self, dest):
        """
        parms:
            dest: [Port] destination port.
        """
        self.dest = dest

#    def handleLocalControl(self, event):
#        self.zyn.sendEvent(event)
#
#    def handleMixerControl(self, event):
#        if event.controller == 74:
#            # send
#        if event.controller ==

    def __call__(self, event):
        self.dest.sendEvent(event)
#        if isinstance(event, SysStart):
#            self.
#        elif isinstance(event, SysStop):
#            self.
#
#        elif isinstance(event, Control
