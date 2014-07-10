from mawb_pb2 import RPC, RECORD, IDLE, PLAY
import socket
import struct

import sys

command = sys.argv[1]
rpc = RPC()

if command == 'record':
    rpc.set_ticks.append(0)
    rpc.change_sequencer_state = RECORD
elif command == 'stop':
    rpc.change_sequencer_state = IDLE
elif command == 'play':
    rpc.set_ticks.append(0)
    rpc.change_sequencer_state = PLAY
elif command == 'echo':
    rpc.echo.append('test of RPC interface')

parcel = rpc.SerializeToString()
data = struct.pack('<I', len(parcel)) + parcel

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
s.connect(('127.0.0.1', 8193))
s.send(data)

