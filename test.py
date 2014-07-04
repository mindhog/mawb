from mawb_pb2 import RPC
import socket
import struct

rpc = RPC()
rpc.echo.append('test of RPC interface')
parcel = rpc.SerializeToString()
data = struct.pack('<I', len(parcel)) + parcel

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
s.connect(('127.0.0.1', 8193))
s.send(data)

