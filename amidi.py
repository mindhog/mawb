"""ALSA midi wrapper."""

import alsa_midi
from midi import Event, NoteOn, NoteOff, PitchWheel, ProgramChange, \
    ControlChange, SysEx

class Shorthand:
    """Class to elide name prefixes, giving us shorter versions of names."""

    def __init__(self, module, prefix):
        self.__mod = module
        self.__pfx = prefix

    def __getattr__(self, attr):
        val = getattr(self.__mod, self.__pfx + attr)
        setattr(self, attr, val)
        return val

ss = Shorthand(alsa_midi, 'snd_seq_')
ssci = Shorthand(alsa_midi, 'snd_seq_client_info_')
sspi = Shorthand(alsa_midi, 'snd_seq_port_info_')
ssps = Shorthand(alsa_midi, 'snd_seq_port_subscribe_')
SS = Shorthand(alsa_midi, 'SND_SEQ_')
SSP = Shorthand(alsa_midi, 'SND_SEQ_PORT_')
SSE = Shorthand(alsa_midi, 'SND_SEQ_EVENT_')

class UnknownEvent(Event):
    """Created when we get an event type that we don't support yet."""

def makeEvent(rawEvent, time = 0):
    """Create a midi event from a raw event received from the sequencer.
    """
    eventData = rawEvent.data
    if rawEvent.type == SSE.NOTEON:
        result = NoteOn(time, eventData.note.channel, EventData.note.node,
                        eventData.note.velocity
                        )
    elif rawEvent.type == SSE.NOTEOFF:
        result = NoteOff(time, eventData.note.channel, eventData.note.note, 0)
    elif rawEvent.type == SSE.PITCHBEND:
        result = PitchWheel(time, eventData.control.channel,
                            eventData.control.value
                            )
    elif rawEvent.type == SSE.PGMCHANGE:
        result = ProgramChange(time, eventData.control.channel,
                               eventData.control.value
                               )
    elif rawEvent.type == SSE.CONTROLLER:
        result = ControlChange(time, eventData.control.channel,
                               eventData.control.value
                               )
    elif rawEvent.type == SSE.SYSEX:
        # XXX need a translator to support sysex events as they have a pointer
        # to external data.
        result = SysEx(time, '')
    else:
        result = UnknownEvent(time, rawEvent.type)

    result._amidi_raw = rawEvent
    return result

def makeRawEvent(event):
    """Returns a new raw event for the high-level midi event."""
    raw = getattr(event, '_amidi_raw', None)
    if raw:
        return raw

    raw = ss.event_t_new()
    ss.ev_set_fixed(raw)
    if isinstance(event, NoteOn):
        raw.type = SSE.NOTEON
        raw.data.note.channel = event.channel
        raw.data.note.note = event.note
        raw.data.note.velocity = event.velocity
    elif isinstance(event, NoteOff):
        raw.type = SSE.NOTEOFF
        raw.data.note.channel = event.channel
        raw.data.note.note = event.note
    elif isinstance(event, PitchWheel):
        raw.type = SSE.PITCHBEND
        raw.data.control.channel = event.channel
        raw.data.control.value = event.value
    elif isinstance(event, ProgramChange):
        raw.type = SSE.PGMCHANGE
        raw.data.control.channel = event.channel
        raw.data.control.value = event.program
    elif isinstance(event, ControlChange):
        raw.type = SSE.CONTROLLER
        raw.data.control.channel = event.channel
        raw.data.control.value = event.value
    elif isinstance(event, SysEx):
        raise Exception("Can't send sysex events yet.")
    else:
        raise Exception("Can't send unknown event type.")

    return raw

class ClientInfo(object):
    """A wrapper for raw midi client info."""

    def __init__(self, rawClient):
        self.rep = rawClient
        self.ports = []

    @property
    def name(self):
        return ss.client_info_get_name(self.rep)

class PortInfo(object):
    """A wrapper for raw midi port info."""

    def __init__(self, rawClient, rawPort):
        self.client = rawClient
        self.rep = rawPort

    @property
    def name(self):
        return ss.port_info_get_name(self.rep)

    @property
    def addr(self):
        return ss.port_info_get_addr(self.rep)

    def __str__(self):
        return '%s/%s' % (ss.client_info_get_name(self.client), self.name)

class Sequencer(object):
    """An ALSA MIDI sequencer."""

    def __init__(self, streams, mode):
        """
            streams: some combination of SND_SEQ_OPEN_OUTPUT and
                SND_SEQ_OPEN_INPUT.
            mode: don't know what this is, safe to use 0.
        """
        rc, self.__seq = ss.open("default", streams, mode)
        if rc:
            raise Exception('Failed to open client, rc = %d' % rc)

    def __wrapWithPortInfo(self, portNum):
        rc, portInfo = ss.port_info_malloc()
        assert not rc
        rc, clientInfo = ss.client_info_malloc()
        assert not rc

        ss.get_port_info(self.__seq, portNum, portInfo)
        ss.get_client_info(self.__seq, clientInfo)
        return PortInfo(clientInfo, portInfo)

    def createInputPort(self, name):
        return self.__wrapWithPortInfo(
            ss.create_simple_port(self.__seq, name,
                                  SSP.CAP_WRITE | SSP.CAP_SUBS_WRITE,
                                  SSP.TYPE_MIDI_GENERIC
                                  )
        )

    def createOutputPort(self, name):
        return self.__wrapWithPortInfo(
            ss.create_simple_port(self.__seq, name,
                                  SSP.CAP_READ | SSP.CAP_SUBS_READ,
                                  SSP.TYPE_MIDI_GENERIC
                                  )
        )

    def iterPorts(self):
        """Iterates over the client, port pairs."""
        rc, cinfo = ss.client_info_malloc()
        assert not rc
        rc, pinfo = ss.port_info_malloc()
        assert not rc
        ssci.set_client(cinfo, -1)
        while ss.query_next_client(self.__seq, cinfo) >= 0:
            ss.port_info_set_client(pinfo, ss.client_info_get_client(cinfo))
            ss.port_info_set_port(pinfo, -1)
            while ss.query_next_port(self.__seq, pinfo) >= 0:
                yield cinfo, pinfo

    def iterPortInfos(self):
        for client, port in self.iterPorts():
            yield PortInfo(client, port)

    def subscribePort(self, subs):
        """
            Args:
                subs: [snd_seq_port_subscribe_t]
        """
        ss.subscribe_port(self.__seq, subs)

    def connectTo(self, port, rmt_client, rmt_port):
        """All args are integers."""
        ss.connect_from(self.__seq, port, rmt_client, rmt_port)

    def connect(self, port1, port2):
        """Connect port1 to port2.

        Args:
            port1: (PortInfo)
            port2: (PortInfo)
        """
        rc, sub = ss.port_subscribe_malloc()
        print sub
        ss.port_subscribe_set_sender(sub, port1.addr)
        ss.port_subscribe_set_dest(sub, port2.addr)
        ss.subscribe_port(self.__seq, sub)
        ss.port_subscribe_free(sub)

    def hasEvent(self):
        return ss.event_input_pending(self.__seq, 1)

    def getEvent(self, time = 0):
        rc, event = ss.event_input(self.__seq)
        return makeEvent(event, time)

    def sendEvent(self, event, port):
        """Send the event to subscribers of the given port.

        Args:
            event: (midi.Event)
            port: (PortInfo)
        """
        raw = makeRawEvent(event)
        ss.ev_set_source(raw, ss.port_info_get_port(port.rep))
        ss.ev_set_subs(raw)
        ss.ev_set_direct(raw)
        ss.event_output(self.__seq, raw)
        ss.drain_output(self.__seq)

    def getPort(self, name):
        """Gets a port of the specified name, None if the port is not defined.

        Args:
            name: (str) Midi port name in the form "client/port".
        """
        client, port = name.split('/')
        for clt, prt in self.iterPorts():
            if client == ss.client_info_get_name(clt) == client and \
               port == ss.port_info_get_name(prt):
                return PortInfo(clt, prt)

        return None

_sequencer = None
def getSequencer():
    global _sequencer
    if not _sequencer:
        _sequencer = Sequencer(SS.OPEN_INPUT | SS.OPEN_OUTPUT, 0)
    return _sequencer