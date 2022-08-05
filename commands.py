# XXX bad version, use the one on succubus instead.

from awb_client import AWBClient
from modes import MidiRoute
#from sci import BadCommandError, SimpleCommandInterface
from typing import Callable, Dict, List

class Program:
    pass

class SimpleCommandInterface:
    pass

class ScriptInterpreter(SimpleCommandInterface):
    """Command interpreter."""

    def __init__(self, commands: Dict[str, callable]):
        super(ScriptInterpreter, self).__init__()
        self.commands = commands

    def _runCommand(self, command: List[str]):
        try:
            func = self.commands[command[0]]
            func(command[1:])
        except KeyError:
            raise BadCommandError(command[0])

    def error(self, ex: Exception):
        raise

class CommandWrapper:

    def __init__(self, command: Callable[[List[str]], None]):
        self.__command = command
        self.__self = None

    def __call__(self, args: List[str]):
        # TODO: coerce args to the appropriate types.
        self.__command(*args)

    def help(self):
        return '%s - %s' % (self.__command.__name__, self.__command.__doc__)

    def getName(self):
        return self.__command.__name__

def command(func):
    func.sci_cmd = True
    return func

class ProgramCommands:

    def __init__(self, client: AWBClient, program: Program):
        self.client = client
        self.program = program
        self.dict = {} # type: Dict[str, CommandWrapper]

        # store all methods in the dictionary.
        for attr in dir(self):
            obj = getattr(self, attr)
            if hasattr(obj, 'sci_cmd'):
                self.dict[attr] = CommandWrapper(obj)

    @command
    def con(self, src: str, dest: str):
        """Connect a source port to a destination port."""
        self.program.routing.routes.append(MidiRoute(src, dest))
