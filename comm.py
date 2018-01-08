"""MAWB python communication module.

Contains code for communicating to the MAWB daemon.
"""

import struct
import subprocess
import time
from spug.io.proactor import getProactor, DataHandler, INETAddress
from mawb_pb2 import PBTrack, SetInitialState, SetInputParams, Response, RPC, \
    RECORD, IDLE, PLAY

class BufferedDataHandler(DataHandler):
    """
        The proactor data handler that manages our connection to the daemon.

        This class is mostly pretty general, and could be refactored out into
        the proactor library.  The process() method should become abstract.
    """

    def __init__(self):
        self.__outputBuffer = ''
        self._inputBuffer = ''
        self.closeFlag = False
        self.control = getProactor().makeControlQueue(self.__onControlEvent)
        self.__messageCallbacks = {}

    def readyToGet(self):
        return self.__outputBuffer

    def readyToPut(self):
        return True

    def readyToClose(self):
        return self.closeFlag

    def peek(self, size):
        return self.__outputBuffer[:size]

    def get(self, size):
        self.__outputBuffer = self.__outputBuffer[size:]

    def put(self, data):
        self._inputBuffer += data
        self.process()

    def process(self):
        """
            This gets called every time data is added to the input buffer.
            It consumes a complete RPC message if there is one and dispatches
            it to the appropriate handler.
        """
        # Return if we don't have a complete message in the buffer.
        if len(self._inputBuffer) < 4:
            return
        size, = struct.unpack('<I', self._inputBuffer[:4])
        if len(self._inputBuffer) < size + 4:
            return

        # Now parse the message.
        serializedMessage = self._inputBuffer[4:size + 4]
        self._inputBuffer = self._inputBuffer[size + 4:]
        resp = Response()
        resp.ParseFromString(serializedMessage)

        # Find the registered callback and call it.
        try:
            callback = self.__messageCallbacks[resp.msg_id]
        except KeyError:
            print('Response received with unknown message id %s' % resp.msg_id)
            return
        try:
            callback(resp)
        except:
            print('Exception in callback:')
            traceback.print_exc()

    def __onControlEvent(self, event):
        """
            Handler for events coming in on the control queue.

            parms:
                event: [str]  Currently this is just data to be added to the
                    out-buffer.
        """
        self.__outputBuffer += event

    # External interface.

    def queueForOutput(self, data):
        """
            Queues a piece of data to be sent over the connection.

            parms:
                data: [str]
        """
        self.control.add(data)

    def registerMessageCallback(self, msgId, callback):
        """
            Registers the function to be called when the response to the
            message with the specified id is received.

            parms:
                msgId: [int] xxx

        """
        self.__messageCallbacks[msgId] = callback

    def close(self):
        """Close the connection."""
        self.control.close()
        self.control.add('')
        self.closeFlag = True

class Comm:
    """The communicator.  Sends RPCs to the daemon."""

    def __init__(self, addr = '127.0.0.1', port = 8193):
        self.handler = BufferedDataHandler()
        self.conn = getProactor().makeConnection(
            INETAddress(addr, port),
            self.handler
        )
        self.__nextMsgId = 0

    def close(self):
        self.handler.close()

    def __getMsgId(self):
        msgId = self.__nextMsgId
        self.__nextMsgId += 1
        return msgId

    def sendRPC(self, **kwargs):
        rpc = RPC()
        if 'callback' in kwargs:
            rpc.msg_id = msgId = self.__getMsgId()
            callback = kwargs['callback']
            self.handler.registerMessageCallback(msgId, callback)
            del kwargs['callback']

        for attr, val in kwargs.items():
            getattr(rpc, attr).CopyFrom(val)

        parcel = rpc.SerializeToString()
        data = struct.pack('<I', len(parcel)) + parcel
        self.handler.queueForOutput(data)

class DaemonManager:
    """Lets you control the daemon."""

    def __init__(self, awbdCmd = ['./awbd']):
        self.daemon = None
        self.awbdCmd = awbdCmd
        self.proxy = None

    def start(self):
        if self.daemon:
            print('Daemon already started.')
            return
        self.daemon = subprocess.Popen(self.awbdCmd)
        self.proxy = Comm()

        # TODO: repeatedly attempt to connect until we can get an "echo" back.
        time.sleep(2)

    def stop(self):
        if self.daemon:
            self.daemon.kill()
            self.daemon.wait()
            self.daemon = None
        else:
            print('Daemon not started.')

    def __del__(self):
        if self.daemon:
            self.stop()


