
import amidi
import jack
import mawb_pb2
import os
import threading
from comm import Comm
from spug.io.proactor import getProactor

class AWBClient(object):
    """AWB Client hub.

    This class manages all client side state and provides methods for
    controlling the collection of programs as well as jack and alsa midi
    connections.

    Attrs:
        seq: [amidi.Sequencer] The sequencer.
        voices: [list<modes.StateVec>] The state vector map, should be one
            per channel.
        state: [modes.StateVec] The current state vector.
    """

    def __init__(self, recordEnabled = False, paused = True):
        self.jack = jack.Client('MAWBSession')
        self.comm = Comm()
        self.seq = amidi.getSequencer()
        self.recordEnabled = recordEnabled
        self.paused = paused
        self.recording = {}
        self.recordChannel = -1
        self.sectionIndex = 0
        self.sectionCount = 1
        self.voices = []
        self.state = None

        # Start the proactor thread.  We do this after Comm() has been
        # created so there are connections to manage, otherwise the proactor
        # will just immediately terminate.
        proactorThread = threading.Thread(target = getProactor().run)
        proactorThread.start()

        self.threadPipeRd, self.threadPipeWr = os.pipe()

        # Configure the deka-pedal.
        # Note: for some reason, this gives back an rc = -1 when run on the pi _after_
        # creating fluidsynth.
        if os.path.exists('/dev/ttyACM0'):
            os.system('stty -F /dev/ttyACM0 cs8 115200 ignbrk -brkint -icrnl -imaxbel '
                    '-opost -onlcr -isig -icanon -iexten -echo -echoe -echok -echoctl '
                    '-echoke noflsh -ixon -crtscts')
            self.pedal = open('/dev/ttyACM0', 'r', False)
        else:
            self.pedal = None

        # Start the pedal handler thread.
        if self.pedal:
            self.pedalThread = threading.Thread(target = self.handlePedal)
            self.pedalThread.start()

    def __convertToPortInfo(self, src):
        """Convert 'src' to PortInfo, if it is PortInfo we just return it."""
        if isinstance(src, amidi.PortInfo): return src
        srcPort = self.seq.getPort(src)
        if not srcPort:
            print 'Port %s not defined' % src
        return srcPort

    def midiConnect(self, src, dst):
        """Connect two midi ports.

        Args:
            src: [str] Source port in "client/port" format.
            dst: [str] Destination port in "client/port" format.
        """
        srcPort = self.__convertToPortInfo(src)
        dstPort = self.__convertToPortInfo(dst)
        if not srcPort or not dstPort: return
        self.seq.connect(srcPort, dstPort)

    def waitForJack(self, portName, timeout=3.0):
        """Wait for a jack port to become available.

        This is used as a way to wait for an external program that we're
        starting to come up.

        Args:
            portName: [str] a jack port name in "client:port" format.

        Raises:
            Exception: On a timeout.
        """
        endTime = time.time() + timeout
        while time.time() < endTime:
            for port in self.jack.get_ports():
                if port.name == portName:
                    return
            time.sleep(0.1)
        raise Exception('timed out waiting for %s' % portName)

    def waitForMidi(self, portName, timeout=3.0):
        """Wait for a midi port to become available.

        This is used as a way to wait for an external program that we're
        starting to come up.

        Args:
            portName: [str] a midi port name in "client/port" format.

        Raises:
            Exception: On a timeout.
        """
        while time.time() < endTime:
            for port in self.seq.iterPortInfos():
                if port.name == portName:
                    return
                time.sleep(0.1)
        raise Exception('timed out waiting for %s' % portName)

    def jackConnect(self, src, dst):
        """Connect two jack ports.

        This won't raise an exception if the connection already exists.

        Args:
            src: [str] a jack source port name in "client:port" format.
            dst: [str] a jack destination port name in "client:port" format.

        Raises:
            jack.JackError: Unable to connect.
        """

        try:
            self.jack.connect(src, dst)
        except jack.JackError as ex:
            if 'already exists' in ex[0]:
                print 'connection already exists'
            else:
                raise

    def jackDisconnectAll(self, port):
        """Disocnnect all connections from the given port.

        Args:
            port: [str] a jack port name in "client:port" format.
        """
        for con in self.jack.get_all_connections(port):
            self.jack.disconnect(port, con)

    def makeMidiOutPort(self, name):
        """Creates a midi output port.

        Args:
            name: [str] A midi port name (this should not include the client
                name, the resulting port will be in the system's client.

        Returns:
            [amidi.PortInfo]
        """
        return self.seq.createOutputPort(name)

    def endRecord(self, channel):
        req = mawb_pb2.ChangeJackStateRequest()
        req.state = mawb_pb2.PLAY
        self.comm.sendRPC(change_jack_state = req)
        self.recording[channel] = False
        self.recordChannel = -1

    def startRecord(self, channel):
        # If we're recording on another channel, mark that we've ended it.
        if self.recordChannel >= 0:
            self.recording[self.recordChannel] = False

        req = mawb_pb2.ChangeJackStateRequest()
        req.state = mawb_pb2.RECORD
        req.channel = channel
        self.comm.sendRPC(change_jack_state = req)
        self.recording[channel] = True
        self.recordChannel = channel
        self.paused = False

    def clearAllState(self):
        self.comm.sendRPC(clear_state = mawb_pb2.ClearStateRequest())
        self.sectionIndex = 0
        self.sectionCount = 1

    def togglePause(self):
        """Toggle pause/play of the daemon."""
        req = mawb_pb2.ChangeJackStateRequest()
        req.state = mawb_pb2.PLAY if self.paused else mawb_pb2.IDLE
        self.comm.sendRPC(change_jack_state = req)
        self.paused = not self.paused

    def activate(self, channel):
        """Activate the state vector for the specified channel.

        Activates the state vector for the channel, setting up the instrument
        programs and routing.

        Args:
            channel: [int] The channel index.
        """
        self.voices[channel].activate(self.state)
        self.state = self.voices[channel]

    def handlePedal():
        """Background thread for processing pedal input."""

        # "closed clean" means that we ended the record of the last channel by
        # a press of the channel's pedal.  In this case, we don't want to start
        # recording when the pedal is released.
        closedClean = False

        while True:
            rdx, wrx, erx = select.select([self.pedal, threadPipeRd], [], [])
            if threadPipeRd in rdx:
                break

            action = self.pedal.read(1)
            action = ord(action)
            release = False
            if action & 0x80:
                action = action & 0x7F
                release = True

            if action in (8, 9):
                if release:
                    continue

                req = mawb_pb2.ChangeSectionRequest()
                if action == 8:
                    req.sectionIndex = -1
                    print 'setting to previous section'
                elif action == 9:
                    if self.sectionIndex == self.sectionCount - 1:
                        print 'sending new section request'
                        sectionCount += 1
                        self.comm.sendRPC(new_section = mawb_pb2.NewSectionRequest())
                        continue
                    print 'changing section index'
                    req.sectionIndex = 1

                self.comm.sendRPC(change_section = req)
                continue

            if release:
                # If we're releasing, start recording on the channel
                if not closedClean:
                    if self.recordEnabled: self.startRecord(channel)
                else:
                    # Clear out the previous closedClean.
                    closedClean = False

            else:
                # Initial press: change the voices.
                channel = action
                self.activate(channel)

                # if we're currently recording on that channel, end the record.
                if self.recording.get(channel):
                    self.endRecord(channel)
                    closedClean = True

    def stop(self):
        self.comm.close()
        if self.pedal:
            os.write(self.threadPipeWr, 'end')
            self.pedalThread.join()
