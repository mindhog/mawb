"""Instrument modes for channels.

"""

from abc import abstractmethod, ABCMeta
from collections import defaultdict
from midi import ControlChange, ProgramChange

class SubState(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def __eq__(self, other):
        raise NotImplementedError()

    def __ne__(self, other):
        return not self == other

    @abstractmethod
    def activate(self):
        raise NotImplementedError()

class MidiState(SubState):

    def __init__(self, seq, port, bank, program):
        self.seq = seq
        self.port = port
        self.bank = bank
        self.program = program

    def __eq__(self, other):
        return self is other or \
                self.bank == other.bank and \
                self.program == other.program

    def activate(self):
        self.seq.sendEvent(ControlChange(0, 0, 0, self.bank >> 7), self.port)
        self.seq.sendEvent(ControlChange(0, 0, 32, self.bank & 127), self.port)
        self.seq.sendEvent(ProgramChange(0, 0, self.program), self.port)

class Route(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def getCurrentOutbounds(self, context):
        """Returns the list of all outbound connections from the source port
        as a list of keys.

        Keys should be compatible with the values returned from getDestKey().

        Args:
            context: [Routing] The routing object, which should contain
                everything that the Route object needs to examine and modify
                system state.
        """

    @abstractmethod
    def getSourceKey(self):
        """Returns the source key for a given connection."""

    @abstractmethod
    def getDestKey(self):
        """Returns the destination key for a given connection."""

    @abstractmethod
    def disconnect(self, context, destKey):
        """Remove the system connection from the source port to the
        destination key.

        Args:
            context: [Routing] See getCurrentOutbounds.
            destKey: [object] A key compatible with that returned from
                getDestKey().
        """

    @abstractmethod
    def connect(self, context):
        """Connect the route.

        Args:
            context: [Routing] See getCurrentOutbounds.
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

    def getCurrentOutbounds(self, context):
        port = context.seq.getPort(self.src)
        return [str(sub) for sub in context.seq.iterSubs(port)]

    def disconnect(self, context, destKey):
        context.seq.disconnect(context.seq.getPort(self.src),
                               context.seq.getPort(destKey)
                               )

    def connect(self, context):
        context.seq.connect(context.seq.getPort(self.src),
                            context.seq.getPort(self.dst)
                            )

class JackRoute(RouteImpl):

    def getCurrentOutbounds(self, context):
        return [
            port.name for port in context.jack.get_all_connections(self.src)
        ]

    def disconnect(self, context, destKey):
        context.jack.disconnect(self.src, destKey)

    def connect(self, context):
        context.jack.connect(self.src, self.dst)

class Routing(SubState):
    """A set of jack audio or midi routes.

    When establishing a set of routes, we clear all connections from all
    source ports in the routing that are not already connected to their
    destination ports.
    """

    def __init__(self, jackClient, seq, *routes):
        """Constructor.

        args:
            jackClient: the Jack client object.
            seq: [amidi.Sequencer]
            *routes: [list(Route)] A list of routes.
        """
        self.jack = jackClient
        self.seq = seq
        self.routes = routes

    def __eq__(self, other):
        return self is other or \
            self.routes == other.routes

    def activate(self):

        # Mapping of all routes for a given port.  The keys can be whatever
        # works for a route type, as returned by getSourceKey()
        routesBySource = defaultdict(list)
        for route in self.routes:
            routesBySource[route.getSourceKey()].append(route)

        # Go through the source ports, remove all existing connections that
        # aren't in the new connections and add all new connections that aren't
        # in the existing connections.
        for routes in routesBySource.itervalues():

            # Convert the routes to a map indexed by destination ports.
            routeMap = dict((route.getDestKey(), route) for route in routes)

            # Go through the existing outbound connections, remove the ones
            # that aren't in the set of desired routes and remove the ones
            # that are from the set of routes that we need to connect.
            for dest in routes[0].getCurrentOutbounds(self):
                try:
                    del routeMap[dest]
                except KeyError:
                    # We don't want to preserve this connection.  Remove it.
                    routes[0].disconnect(self, dest)

            # connect everything remaining in the routeMap (only the
            # connections that we want but don't currently exist should
            # remain).
            for route in routeMap.itervalues():
                route.connect(self)

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

    def __getattr__(self, name):
        try:
            return self.__dict[name]
        except KeyError as ex:
            raise AttributeError(ex[0])

    def __hasattr__(self, name):
        return self.__dict.has_key(name)

    def activate(self, curState):
        """Activate the reciver.

        Args:
            curState: (SubState or None) the existing state.
        """
        for name, val in self.__dict.iteritems():
            if not hasattr(curState, name) or getattr(curState, name) != val:
                val.activate()
