
from unittest import main, TestCase
from midi import ControlChange, ProgramChange
from modes import MidiRoute, MidiState, Route, Routing, StateVec

class FakeSequencer(object):

    class Port(object):
        def __init__(self, name):
            self.name = name

        def __str__(self):
            return self.name

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

class StateVecTest(TestCase):

    def testAttrs(self):
        vec = StateVec(foo = 1, bar = 2)
        self.assertEqual(vec.foo, 1)
        self.assertEqual(vec.bar, 2)

        vec.baz = 'more data'
        self.assertEqual(vec.baz, 'more data')

    def testTransitions(self):
        seq = FakeSequencer()
        state1 = StateVec(foo = MidiState(seq, seq.Port, 129, 10),
                          bar = MidiState(seq, seq.Port, 129, 11),
                          baz = MidiState(seq, seq.Port, 5, 10)    # Inert
                          )
        state2 = StateVec(foo = MidiState(seq, seq.Port, 130, 12), # Changed
                          bar = MidiState(seq, seq.Port, 129, 11), # Unchanged.
                          )

        state2.activate(state1)

        self.assertEqual(seq.events,
                         [(ControlChange(0, 0, 0, 1), seq.Port),
                          (ControlChange(0, 0, 32, 2), seq.Port),
                          (ProgramChange(0, 0, 12), seq.Port),
                          ]
                         )

    def testInertStateActivation(self):
        seq = FakeSequencer()
        state1 = StateVec()
        state2 = StateVec(foo = MidiState(seq, seq.Port, 10, 20))
        state2.activate(state1)
        self.assertEqual(seq.events,
                         [(ControlChange(0, 0, 0, 0), seq.Port),
                          (ControlChange(0, 0, 32, 10), seq.Port),
                          (ProgramChange(0, 0, 20), seq.Port),
                          ]
                         )

class FakeRoute(Route):

    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def getCurrentOutbounds(self, context):
        return ['foo', 'bar']

    def getSourceKey(self):
        return self.src

    def getDestKey(self):
        return self.dst

    def disconnect(self, context, destKey):
        context.collector.append('disconnect %s, %s' % (self.src, destKey))

    def connect(self, context):
        context.collector.append('connect %s, %s' % (self.src, self.dst))

    def __eq__(self, other):
        return isinstance(other, FakeRoute) and \
            self.src == other.src and \
            self.dst == other.dst

class RoutingTest(TestCase):

    def testRouting(self):
        routing = Routing(None, None,
                          FakeRoute('a', 'b'),
                          FakeRoute('c', 'd'),
                          FakeRoute('c', 'bar')
                          )
        routing.collector = []
        routing.activate()
        self.assertEqual(routing.collector,
                         ['disconnect a, foo', 'disconnect a, bar',
                          'connect a, b', 'disconnect c, foo', 'connect c, d'
                          ]
                         )

    def testEquality(self):
        self.assertEqual(Routing(None, None, FakeRoute('a', 'b')),
                         Routing(None, None, FakeRoute('a', 'b')))

    def testMidiRoutes(self):
        route = MidiRoute('a', 'b')
        self.assertEqual(route.getCurrentOutbounds(
                             Routing(None, FakeSequencer())
                         ),
                         ['1', '2', '3']
                         )
        self.assertEqual(route.getSourceKey(), 'a')
        self.assertEqual(route.getDestKey(), 'b')

        seq = FakeSequencer()
        route.disconnect(Routing(None, seq), 'x')
        self.assertEqual(seq.events, ['disconnect a, x'])

        seq = FakeSequencer()
        route.connect(Routing(None, seq))
        self.assertEqual(seq.events, ['connect a, b'])

if __name__ == '__main__':
    main()
