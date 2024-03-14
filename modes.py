"""Instrument modes for channels.

"""

from abc import abstractmethod, ABCMeta
from collections import defaultdict
import copy
from midi import ControlChange, ProgramChange

class SubState(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def __eq__(self, other):
        raise NotImplementedError()

    def __ne__(self, other):
        return not self == other

    @abstractmethod
    def activate(self, client):
        """Interface to activate a substate.

        parms:
            client: [awb_client.Client]
        """
        raise NotImplementedError()

class MidiState(SubState):

    def __init__(self, portName, bank, program, channel=0):
        assert isinstance(portName, str)
        self.portName = portName
        self.bank = bank
        self.program = program
        self.channel = channel

    def __eq__(self, other):
        return self is other or \
                isinstance(other, MidiState) and \
                self.portName == other.portName and \
                self.bank == other.bank and \
                self.program == other.program and \
                self.channel == other.channel

    def clone(self):
        return MidiState(self.portName, self.bank, self.program, self.channel)

    def activate(self, client):
        port = client.seq.getPort(self.portName)
        client.seq.sendEvent(ControlChange(0, self.channel, 0, self.bank >> 7),
                             port)
        client.seq.sendEvent(ControlChange(0, self.channel, 32, self.bank & 127),
                             port)
        client.seq.sendEvent(ProgramChange(0, self.channel, self.program), port)

class Route(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def getCurrentOutbounds(self, client):
        """Returns the list of all outbound connections from the source port
        as a list of keys.

        Keys should be compatible with the values returned from getDestKey().

        parms:
            client: [awb_client.Client]
        """

    @abstractmethod
    def getSourceKey(self):
        """Returns the source key for a given connection."""

    @abstractmethod
    def getDestKey(self):
        """Returns the destination key for a given connection."""

    @abstractmethod
    def disconnect(self, client, destKey):
        """Remove the system connection from the source port to the
        destination key.

        Args:
            client: [awb_client.Client] See getCurrentOutbounds.
            destKey: [object] A key compatible with that returned from
                getDestKey().
        """

    @abstractmethod
    def connect(self, client):
        """Connect the route.

        Args:
            client: [awb_client.Client] See getCurrentOutbounds.
        """

    @abstractmethod
    def __eq__(self, other):
        pass

class RouteImpl(Route):
    """Partial route implementation for routes whose keys are simple
    strings.
    """

    def __init__(self, src, dst):
        """
        Args:
            src: [str] name of source port ("client/port")
            dst: [str] name of destination port ("client/port")
        """
        self.src = src
        self.dst = dst

    def getSourceKey(self):
        return self.src

    def getDestKey(self):
        return self.dst

    def __eq__(self, other):
        return isinstance(other, RouteImpl) and \
            self.src == other.src and \
            self.dst == other.dst

class MidiRoute(RouteImpl):

    def getCurrentOutbounds(self, client):
        port = client.seq.getPort(self.src)
        return [str(sub) for sub in client.seq.iterSubs(port)]

    def disconnect(self, client, destKey):
        client.seq.disconnect(client.seq.getPort(self.src),
                              client.seq.getPort(destKey)
                              )

    def connect(self, client):
        client.seq.connect(client.seq.getPort(self.src),
                           client.seq.getPort(self.dst)
                           )

class JackRoute(RouteImpl):

    def getCurrentOutbounds(self, client):
        return [
            port.name for port in client.jack.get_all_connections(self.src)
        ]

    def disconnect(self, client, destKey):
        client.jack.disconnect(self.src, destKey)

    def connect(self, client):
        client.jack.connect(self.src, self.dst)

class Routing(SubState):
    """A set of jack audio or midi routes.

    When establishing a set of routes, we clear all connections from all
    source ports in the routing that are not already connected to their
    destination ports.
    """

    def __init__(self, *routes: Route):
        """Constructor.

        args:
            *routes: A list of routes.
        """
        self.routes = list(routes)

    def __eq__(self, other):
        return self is other or \
            self.routes == other.routes

    def activate(self, client):

        # Mapping of all routes for a given port.  The keys can be whatever
        # works for a route type, as returned by getSourceKey()
        routesBySource = defaultdict(list)
        for route in self.routes:
            routesBySource[route.getSourceKey()].append(route)

        # Go through the source ports, remove all existing connections that
        # aren't in the new connections and add all new connections that aren't
        # in the existing connections.
        for routes in routesBySource.values():

            # Convert the routes to a map indexed by destination ports.
            routeMap = dict((route.getDestKey(), route) for route in routes)

            # Go through the existing outbound connections, remove the ones
            # that aren't in the set of desired routes and remove the ones
            # that are from the set of routes that we need to connect.
            for dest in routes[0].getCurrentOutbounds(client):
                try:
                    del routeMap[dest]
                except KeyError:
                    # We don't want to preserve this connection.  Remove it.
                    routes[0].disconnect(client, dest)

            # connect everything remaining in the routeMap (only the
            # connections that we want but don't currently exist should
            # remain).
            for route in routeMap.values():
                try:
                    route.connect(client)
                except Exception as ex:
                    print('error connecting %s: %s' % (route, ex))

class StateVec(object):
    """A state vector.

    xxx TransitionVect?
    """

    def __init__(self, **kwargs):
        self.__dict = kwargs

    def __setattr__(self, name, val):
        if name == '_StateVec__dict':
            object.__setattr__(self, name, val)
        else:
            self.__dict[name] = val

    def __delattr__(self, name):
        del self.__dict[name]

    def __getattr__(self, name):
        if name == '_StateVec_dict':
            raise AttributeError('_StateVec_dict')
        try:
            return self.__dict[name]
        except KeyError as ex:
            raise AttributeError(str(ex))

    def __dir__(self):
        return self.__dict.keys()

    def __hasattr__(self, name):
        return self.__dict.has_key(name)

    def __setstate__(self, dict):
        self.__dict = dict['_StateVec__dict']

    def clone(self):
        return copy.deepcopy(self)

    def activate(self, client, curState):
        """Activate the reciver.

        Args:
            client: (awb_client.Client) The awb client, which gets passed to
                all substates to be activated.
            curState: (SubState or None) the existing state.
        """
        for name, val in self.__dict.items():
            if not hasattr(curState, name) or getattr(curState, name) != val:
                val.activate(client)
