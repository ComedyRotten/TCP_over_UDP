import getopt
import sys
from random import randint

import BasicSender
import Checksum


class Sender(BasicSender.BasicSender):

    def __init__(self, dest, port, filename, listenport=33122, debug=False, timeout=10):
        super().__init__(dest, port, filename, debug)
        self.rtimeout = timeout
        self.MESSAGE_HANDLER = {
            'ack': self._handle_ack
        }

    '''
    Main sender loop:
    1. Send a 'start' message to the specified receiver address that contains the following:
        msgtype='start' seqno=N data='' chksum=CHECKSUM
        where N = random initial integer within given range and CHECKSUM is the calculated checksum for the entire 
        message packet (minus the checksum itself).
    2. Wait for an 'ack' message to return and verify that the host received the 'start'.
    3. Continue sending data using the 'data' message types; mark each as successfully sent  when the ack is returned.
        The above could be implemented as a 2D array: x=data y=acknowledged flag
        The 2D array could also have a list that pulls from the 2D array that acts as the sliding window.
    4. When all data is sent and acknowledged, send an 'end' packet and close the connection.
    '''
    def start(self):
        # load the file into the two-dimensional list
        # Initialize another 2D list to act as the sliding window.
        # May be worth implementing the resilient Receiver that accepts packets out of order (fairly easy?)

        # Send initial 'start' packet to the receiver
        self.send(self.make_packet('start', randint(0, 4096), b'Start message!'), (self.dest, self.dport))

        # Main sending loop.
        while True:
            # Receive the message and where it came from
            message, address = self.receive()
            # Split the message up into it's appropriate parts
            msg_type, seqno, data, checksum = self.split_packet(message)
            # Try and handle the message depending on it's type
            try:
                seqno = int(seqno)
            except:
                raise ValueError
            if not debug:
                print('Split message: {0} {1} {2} {3}'.format(msg_type, seqno, data, checksum))
            if Checksum.validate_checksum(message):
                # If the checksum checks out, handle the message using one of the following methods defined by the
                # MESSAGE_HANDLER dictionary.
                self.MESSAGE_HANDLER.get(msg_type, self._handle_other)(seqno, data, address)
            elif self.debug:
                print("checksum failed: %s" % message)

    def load_file(self,fname):
        # Read in a file and split the input file into data chunks and return data chunks.
        pass

    # I'll do the ack-ing here, buddy
    def _handle_ack(self, seqno, data, address):
        print("start received: seqno: {0}  address: {1}".format(seqno, address))
        pass

    # handler for packets with unrecognized type
    def _handle_other(self, seqno, data, address):
        print("start received: seqno: {0}  address: {1}".format(seqno, address))
        pass



'''
This will be run if you run this script from the command line. You should not
change any of this; the grader may rely on the behavior here to test your
submission.
'''
if __name__ == "__main__":
    def usage():
        print ("Sender")
        print ("-f FILE | --file=FILE The file to transfer; if empty reads from STDIN")
        print ("-p PORT | --port=PORT The destination port, defaults to 33122")
        print ("-a ADDRESS | --address=ADDRESS The receiver address or hostname, defaults to localhost")
        print ("-d | --debug Print debug messages")
        print ("-h | --help Print this usage message")

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                               "f:p:a:d", ["file=", "port=", "address=", "debug="])
    except:
        usage()
        exit()

    port = 33122
    dest = "localhost"
    filename = None
    debug = False

    for o,a in opts:
        if o in ("-f", "--file="):
            filename = a
        elif o in ("-p", "--port="):
            port = int(a)
        elif o in ("-a", "--address="):
            dest = a
        elif o in ("-d", "--debug="):
            debug = True

    s = Sender(dest,port,filename,debug)
    try:
        s.start()
    except (KeyboardInterrupt, SystemExit):
        exit()
