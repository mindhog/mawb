
import subprocess
import time
import socket

awbdCommand = ['awbd']

debug = False
if debug:
    awbdCommand.insert(0, 'gdb')

daemon = subprocess.Popen(awbdCommand)
time.sleep(1)
if debug:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    s.bind(('localhost', 9191))
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.listen(5)
    s.accept()

subprocess.call(['aconnect', '130:0', '129:1'])
subprocess.call(['jack_connect', 'fluidsynth:l_00', 'system:playback_1'])
subprocess.call(['jack_connect', 'fluidsynth:r_00', 'system:playback_2'])

daemon.wait()

