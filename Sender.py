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
    
    Message format:
    The message is 1472 bytes divided up into the following:
    5 bytes: msgtype (to accomodate 'start' flag)
    4 bytes: seqno
    1458 bytes: message/data
    2 bytes: checksum
    3 bytes: packet delimiters '|'
    '''
    def start(self):
        # Send initial 'start' packet to the receiver
        # The initial seqno is set to a random a 16-bit int (2 bytes).
        self.current_seqno = randint(0, 65535)

        # load the file into the two-dimensional list
        # Initialize another 2D list to act as the sliding window.
        # May be worth implementing the resilient Receiver that accepts packets out of order (fairly easy?)
        self.msg_queue, self.msg_window = self.load_file(filename, self.current_seqno)

        self.send(self.make_packet('start', self.msg_queue[0][1], self.msg_queue[0][0]), (self.dest, self.dport))

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

    def load_file(self, fname, sn):
        # Read in a file and split the input file into data chunks and return data chunks.
        # The file is converted to a bytestream that reads in the file, either reading in only what is necessary and
        # putting that into the msg_window, or reading in the entire file into a 2D list where each element represents
        # a (data (bytearray), seqno (int), acknowledged (bool)) data pair. The seqno is set here to the initial value
        # and incremented by the number of bytes in the current packet.
        current_seqno = sn
        msg_queue = ((b'Hello World...',current_seqno + sys.getsizeof(b'Hello World...'), False))
        current_seqno += sys.getsizeof(b'Hello World...')
        msg_window = ()
        return msg_queue, msg_window

    # Handle an 'ack' reply from the server
    def _handle_ack(self, seqno, data, address):
        print("start received: seqno: {0}  address: {1}".format(seqno, address))
        # Check the seqno to verify whether the packet is the current packet

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
