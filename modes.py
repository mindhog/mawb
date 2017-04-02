"""Instrument modes for channels.

"""

from abc import abstractmethod, ABCMeta
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
