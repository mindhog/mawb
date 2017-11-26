
from collections import namedtuple
from unittest import main, TestCase
from midi import ControlChange, ProgramChange
from modes import JackRoute, MidiRoute, MidiState, RouteImpl, Routing, StateVec

class FakeSequencer(object):

    class Port(object):
        def __init__(self, name):
            self.name = name

        def __str__(self):
            return self.name

        def __repr__(self):
            return 'Port(%s)' % self.name

        def __eq__(self, other):
            return self.name == other.name

        def __cmp__(self, other):
            return cmp(self.name, other.name)

    def __init__(self):
        self.events = []

    def sendEvent(self, event, port):
        self.events.append((event, port))

    def getPort(self, src):
        return self.Port(src)

    def iterSubs(self, port):
        return [1, 2, 3]

    def disconnect(self, port1, port2):
        self.events.append('disconnect %s, %s' % (port1, port2))

    def connect(self, port1, port2):
        self.events.append('connect %s, %s' % (port1, port2))

class FakeClient(object):

    def __init__(self, seq):
        self.seq = seq
        self.collector = []

class FakeJack(object):

    class Port(object):
        def __init__(self, name):
            self.name = name

    def __init__(self):
        self.events = []

    def get_all_connections(self, port):
        return [self.Port('x'), self.Port('y')]

    def connect(self, port1, port2):
        self.events.append('connect %s, %s' % (port1, port2))

    def disconnect(self, port1, port2):
        self.events.append('disconnect %s, %s' % (port1, port2))

class StateVecTest(TestCase):

    def testAttrs(self):
        vec = StateVec(foo = 1, bar = 2)
        self.assertEqual(vec.foo, 1)
        self.assertEqual(vec.bar, 2)

        vec.baz = 'more data'
        self.assertEqual(vec.baz, 'more data')

    def testTransitions(self):
        seq = FakeSequencer()
        client = FakeClient(seq)
        state1 = StateVec(foo = MidiState('port1', 129, 10),
                          bar = MidiState('port2', 129, 11),
                          baz = MidiState('port3', 5, 10)    # Inert
                          )
        state2 = StateVec(foo = MidiState('port1', 130, 12), # Changed
                          bar = MidiState('port2', 129, 11), # Unchanged.
                          )

        state2.activate(client, state1)

        self.assertEqual(seq.events,
                         [(ControlChange(0, 0, 0, 1), seq.Port('port1')),
                          (ControlChange(0, 0, 32, 2), seq.Port('port1')),
                          (ProgramChange(0, 0, 12), seq.Port('port1')),
                          ]
                         )

    def testInertStateActivation(self):
        seq = FakeSequencer()
        client = FakeClient(seq)
        state1 = StateVec()
        state2 = StateVec(foo = MidiState('port1', 10, 20))
        state2.activate(client, state1)
        self.assertEqual(seq.events,
                         [(ControlChange(0, 0, 0, 0), seq.Port('port1')),
                          (ControlChange(0, 0, 32, 10), seq.Port('port1')),
                          (ProgramChange(0, 0, 20), seq.Port('port1')),
                          ]
                         )

class FakeRoute(RouteImpl):

    def getCurrentOutbounds(self, client):
        return ['foo', 'bar']

    def disconnect(self, client, destKey):
        client.collector.append('disconnect %s, %s' % (self.src, destKey))

    def connect(self, client):
        client.collector.append('connect %s, %s' % (self.src, self.dst))

class RoutingTest(TestCase):

    def testRouting(self):
        client = FakeClient(None)
        routing = Routing(FakeRoute('a', 'b'),
                          FakeRoute('c', 'd'),
                          FakeRoute('c', 'bar')
                          )
        routing.collector = []
        routing.activate(client)
        self.assertEqual(client.collector,
                         ['disconnect a, foo', 'disconnect a, bar',
                          'connect a, b', 'disconnect c, foo', 'connect c, d'
                          ]
                         )

    def testEquality(self):
        self.assertEqual(Routing(None, None, FakeRoute('a', 'b')),
                         Routing(None, None, FakeRoute('a', 'b')))

    def testRouteImpl(self):
        # We can use FakeRoute because it's derived from RouteImpl.
        route = FakeRoute('a', 'b')
        self.assertEqual(route.getSourceKey(), 'a')
        self.assertEqual(route.getDestKey(), 'b')
        self.assertEqual(route, FakeRoute('a', 'b'))
        self.assertNotEqual(route, FakeRoute('c', 'd'))
        self.assertNotEqual(route, namedtuple('Foo', 'src dst')('a', 'b'))

    def testMidiRoutes(self):
        seq = FakeSequencer()
        client = FakeClient(seq)
        route = MidiRoute('a', 'b')
        self.assertEqual(route.getCurrentOutbounds(client),
                         ['1', '2', '3']
                         )

        route.disconnect(client, 'x')
        self.assertEqual(seq.events, ['disconnect a, x'])
        seq.events = []

        route.connect(client)
        self.assertEqual(seq.events, ['connect a, b'])

    def testJackRoutes(self):
        client = FakeClient(FakeSequencer())
        client.jack = FakeJack()
        route = JackRoute('a', 'b')
        self.assertEqual(route.getCurrentOutbounds(client),
                         ['x', 'y']
                         )
        self.assertEqual(route.getSourceKey(), 'a')

        client.jack = FakeJack()
        route.disconnect(client, 'x')
        self.assertEqual(client.jack.events, ['disconnect a, x'])

        client.jack = FakeJack()
        route.connect(client)
        self.assertEqual(client.jack.events, ['connect a, b'])

if __name__ == '__main__':
    main()
