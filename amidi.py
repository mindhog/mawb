"""ALSA midi wrapper."""

from __future__ import annotations

import alsa_midi # type: ignore (this doesn't work)
from midi import Event, NoteOn, NoteOff, PitchWheel, ProgramChange, \
    ControlChange, SysContinue, SysEx, SysStart, SysStop
from select import POLLIN
from shorthand import Shorthand
from typing import Generator

ss = Shorthand(alsa_midi, 'snd_seq_')
ssci = Shorthand(alsa_midi, 'snd_seq_client_info_')
sspi = Shorthand(alsa_midi, 'snd_seq_port_info_')
ssps = Shorthand(alsa_midi, 'snd_seq_port_subscribe_')
SS = Shorthand(alsa_midi, 'SND_SEQ_')
SSP = Shorthand(alsa_midi, 'SND_SEQ_PORT_')
SSE = Shorthand(alsa_midi, 'SND_SEQ_EVENT_')

class UnknownEvent(Event):
    """Created when we get an event type that we don't support yet."""
    def __init__(self, time, type):
        Event.__init__(self, time)
        self.type = type

    def __str__(self):
        return 't: %s, type: %s' % (self.time, self.type)

def makeEvent(rawEvent, time = 0):
    """Create a midi event from a raw event received from the sequencer.
    """
    eventData = rawEvent.data
    if rawEvent.type == SSE.NOTEON:
        result = NoteOn(time, eventData.note.channel, eventData.note.note,
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
                               eventData.control.param,
                               eventData.control.value
                               )
    elif rawEvent.type == SSE.SYSEX:
        result = SysEx(time, eventData.ext)
    elif rawEvent.type == SSE.START:
        result = SysStart(time)
    elif rawEvent.type == SSE.CONTINUE:
        result = SysContinue(time)
    elif rawEvent.type == SSE.STOP:
        result = SysStop(time)
    else:
        result = UnknownEvent(time, rawEvent.type)

    return result

def makeRawEvent(event):
    """Returns a new raw event for the high-level midi event."""

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
        raw.data.control.param = event.controller
        raw.data.control.value = event.value
    elif isinstance(event, SysEx):
        raw.type = SSE.SYSEX
        ss.event_t_set_ext(raw, event.data)
    else:
        raise Exception("Can't send unknown event type.")

    return raw

class ClientInfo(object):
    """A wrapper for raw midi client info."""

    def __init__(self, seq: Sequencer, client):
        self.seq = seq
        self.rep = client

    def __del__(self):
        ssci.free(self.rep)

    @property
    def name(self):
        return ss.client_info_get_name(self.rep)

    def iterPortInfos(self) -> Generator[PortInfo, None, None]:
        return self.seq._iterPortsForClient(self)

class PortInfo(object):
    """A wrapper for raw midi port info."""

    def __init__(self, client: ClientInfo, rawPort):
        self.client = client
        self.rep = rawPort

    def __del__(self):
        sspi.free(self.rep)

    @property
    def name(self):
        return ss.port_info_get_name(self.rep)

    @property
    def fullName(self):
        return str(self)

    @property
    def addr(self):
        return ss.port_info_get_addr(self.rep)

    def __eq__(self, other):
        otherAddr = other.addr
        addr = self.addr
        return addr.client == otherAddr.client and addr.port == otherAddr.port

    def __str__(self):
        return '%s/%s' % (self.client.name, self.name)

class Sequencer(object):
    """An ALSA MIDI sequencer."""

    def __init__(self, streams, mode, name = None):
        """
            streams: some combination of SND_SEQ_OPEN_OUTPUT and
                SND_SEQ_OPEN_INPUT.
            mode: don't know what this is, safe to use 0.
        """
        rc, self.__seq = ss.open("default", streams, mode)
        if rc:
            raise Exception('Failed to open client, rc = %d' % rc)
        if name:
            ss.set_client_name(self.__seq, name)

    def close(self):
        ss.close(self.__seq)

    def __wrapWithPortInfo(self, portNum, clientId = None):
        rc, portInfo = sspi.malloc()
        assert not rc
        rc, clientInfo = ssci.malloc()
        assert not rc

        if clientId is None:
            ss.get_port_info(self.__seq, portNum, portInfo)
            ss.get_client_info(self.__seq, clientInfo)
        else:
            ss.get_any_port_info(self.__seq, clientId, portNum, portInfo)
            ss.get_any_client_info(self.__seq, clientId, clientInfo)
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

    def deletePort(self, port):
        """Delete a port.

        parms:
            port: [PortInfo]
        """
        ss.delete_simple_port(self.__seq, port.addr.port)

    def getPollHandle(self):
        """Returns a poll handle for the sequencer."""
        fds = alsa_midi.PollfdArray(1)
        assert ss.poll_descriptors(self.__seq, fds.cast(), 1, POLLIN) == 1
        return fds[0].fd

    def iterClientInfos(self) -> Generator[ClientInfo, None, None]:
        """Iterates over the set of clients."""
        rc, cinfo = ss.client_info_malloc()
        assert not rc
        ssci.set_client(cinfo, -1)
        while ss.query_next_client(self.__seq, cinfo) >= 0:
            lastClient = ssci.get_client(cinfo)
            yield ClientInfo(self, cinfo)

            # Allocate a new client info, set the id to the id of the last one
            # so the next query will get the next one.
            rc, cinfo = ssci.malloc()
            assert not rc
            ssci.set_client(cinfo, lastClient)

        # Free memory for the last client, which was never used.
        ssci.free(cinfo)

    def _iterPortsForClient(
            self, client: ClientInfo
    ) -> Generator[PortInfo, None, None]:
        # Allocate a new port object, set it to the first port.
        rc, pinfo = sspi.malloc()
        assert not rc
        sspi.set_client(pinfo, ssci.get_client(client.rep))
        sspi.set_port(pinfo, -1)
        while ss.query_next_port(self.__seq, pinfo) >= 0:
            lastPort = sspi.get_port(pinfo)
            yield PortInfo(client, pinfo)

            # Allocate new port info, set its id to the last port so the
            # next query will get the next one.
            rc, pinfo = sspi.malloc()
            assert not rc
            sspi.set_client(pinfo, ssci.get_client(client.rep))
            sspi.set_port(pinfo, lastPort)

        # Free memory for last port, which was never used.
        sspi.free(pinfo)

    def iterPortInfos(self) -> Generator[PortInfo, None, None]:
        """Iterates over the set of all ports."""
        for client in self.iterClientInfos():
            for port in self._iterPortsForClient(client):
                yield port

    def iterSubs(self, port):
        """Iterate over the subscriptions for the port.

        Yields:
            PortInfo
        """
        rc, subs = ss.query_subscribe_malloc()
        ss.query_subscribe_set_root(subs, port.addr)
        ss.query_subscribe_set_type(subs, SS.QUERY_SUBS_READ)
        index = 0
        ss.query_subscribe_set_index(subs, index)
        while ss.query_port_subscribers(self.__seq, subs) >= 0:
            addr = ss.query_subscribe_get_addr(subs)

            # Get client info and port info objects.
            rc, clientInfo = ss.client_info_malloc()
            ss.get_any_client_info(self.__seq, addr.client, clientInfo)
            rc, portInfo = ss.port_info_malloc()
            ss.get_any_port_info(self.__seq, addr.client, addr.port, portInfo)

            yield PortInfo(clientInfo, portInfo)

            index += 1
            ss.query_subscribe_set_index(subs, index)

    def subscribePort(self, subs):
        """
            Args:
                subs: [snd_seq_port_subscribe_t]
        """
        ss.subscribe_port(self.__seq, subs)

    def connectTo(self, port, rmt_client, rmt_port):
        """All args are integers."""
        ss.connect_from(self.__seq, port, rmt_client, rmt_port)

    def __createSubscription(self, port1: PortInfo, port2: PortInfo):
        """Returns a new subscription object for the two ports."""
        rc, sub = ss.port_subscribe_malloc()
        ss.port_subscribe_set_sender(sub, port1.addr)
        ss.port_subscribe_set_dest(sub, port2.addr)
        return sub

    def connect(self, port1, port2):
        """Connect port1 to port2.

        Args:
            port1: (PortInfo)
            port2: (PortInfo)
        """
        sub = self.__createSubscription(port1, port2)
        ss.subscribe_port(self.__seq, sub)
        ss.port_subscribe_free(sub)

    def disconnect(self, port1, port2):
        """Disconnect two ports."""
        sub = self.__createSubscription(port1, port2)
        ss.unsubscribe_port(self.__seq, sub)
        ss.port_subscribe_free(sub)

    def hasEvent(self):
        return ss.event_input_pending(self.__seq, 1)

    def getEvent(self, time = 0):
        """Waits for an event and returns it.\

        Returns:
            (Event) The event returned has two extra attributes, "source" and
            "dest" which are not part of normal events.  These are PortInfo
            objects for the source and destination ports.
        """
        rc, rawEvent = ss.event_input(self.__seq)
        event = makeEvent(rawEvent, time)
        event.source = self.__wrapWithPortInfo(rawEvent.source.port,
                                               rawEvent.source.client)
        event.dest = self.__wrapWithPortInfo(rawEvent.dest.port,
                                             rawEvent.dest.client)
        return event

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

        Returns:
            [PortInfo]
        """
        for port in self.iterPortInfos():
            if port.fullName == name:
                return port

        return None

_sequencer = None
def getSequencer(name = None):
    global _sequencer
    if not _sequencer:
        _sequencer = Sequencer(SS.OPEN_INPUT | SS.OPEN_OUTPUT, 0, name = name)
    return _sequencer
