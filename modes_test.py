
from unittest import main, TestCase
from midi import ControlChange, ProgramChange
from modes import MidiState, StateVec

class FakeSequencer(object):

    class Port(object):
        pass

    def __init__(self):
        self.events = []

    def sendEvent(self, event, port):
        self.events.append((event, port))

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

if __name__ == '__main__':
    main()
