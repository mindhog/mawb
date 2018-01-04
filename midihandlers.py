"""Midi handlers.  Attach these to AWBClient's dispatchEvent."""

import midi

class PassThrough(object):
    """Forwards all events to another midi port."""

    def __init__(self, dest):
        """
        parms:
            dest: [str] destination port name.
        """
        self.dest = dest

    def __call__(self, client, event):
        client.seq.sendEvent(event, client.seq.getPort(self.dest))

class ChannelFilter(object):
    """A pass-through handler that changes the midi channel.
    """
    def __init__(self, dest, channel):
        """
        parms:
            dest: [str] destination port name.
            channel: [int] the channel to add to all ChannelEvents.
        """
        self.dest = dest
        self.channel = channel

    def __call__(self, client, event):
        if isinstance(event, midi.ChannelEvent):
            print 'changing channel to %d' % self.channel
            event.channel = self.channel
        client.seq.sendEvent(event, client.seq.getPort(self.dest))

class ProgramChangeControl(object):
    """A ControlChange handler that activates a program change."""

    def __init__(self, midiState, programs):
        """Constructor.

        parms:
            midiState: [modes.MidiState] The midi state object to mutate and
                activate.
            programs: [list<tuple<bank: int, program: int>>] List of
                bank/program to be selected based on the controller value.
                Control values map to programs in the list by a scaling
                factor, so when there's a control change:
                    listIndex = listLength * controllerValue / 128
                If the program list has more than 128 elements, some of them
                will not be available.
                The instance takes ownership of this list and may mutate it.
        """
        self.__programs = programs
        self.__midiState = midiState

    def __call__(self, client, event):
        index = event.value * len(self.__programs) / 128
        self.__midiState.bank, self.__midiState.program = \
            self.__programs[index]

class Param(object):
    """Changes a parameter in a SubState to the value of a control."""

    def __init__(self, node, param):
        """Constructor.

        parms:
            node: [modes.SubState] The state object to modify.
            param: [str] The parameter to modify.
        """
        self.__node = node
        self.__param = param

    def __call__(self, client, event):
        setattr(self.__node, self.__param, event.value)
        self.__node.activate(client)

class ControlMap(object):
    """Maps control events to control handlers.

    Passes all other events to nonControlHandler, if one is defined.
    """

    def __init__(self, nonControlHandler=None):
        """
        parms:
            nonControlHandler: [callable<AWBClient, midi.Event>] Fall-through
                handler called for non-control events.
        """
        self.__map = {}
        self.nonControlHandler = nonControlHandler

    def addControlHandler(self, controller, handler):
        """Adds a handler for a midi controller.

        parms:
            controller: [int] Midi controller id.
            handler: [callable<AWBClient, midi.ControlChange>] Handler to
                attach to the control.
        """
        self.__map[controller] = handler

    def __call__(self, client, event):
        if isinstance(event, midi.ControlChange):
            handler = self.__map.get(event.controller)
            if handler:
                handler(client, event)
                return

        elif self.nonControlHandler:
            self.nonControlHandler(client, event)
