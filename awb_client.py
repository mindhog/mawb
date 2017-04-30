
import amidi
import jack

class AWBClient(object):
    """AWB Client hub.

    This class manages all client side state and provides methods for
    controlling the collection of programs as well as jack and alsa midi
    connections.
    """

    def __init__(self):
        self.jack = jack.Client('MAWBSession')
        self.seq = amidi.getSequencer()

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
