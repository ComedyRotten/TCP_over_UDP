import getopt
import sys
import os
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
        # The initial seqno is set to a random a 16-bit int (2 bytes).

        # load the file into the two-dimensional list
        # Initialize another 2D list to act as the sliding window.
        # May be worth implementing the resilient Receiver that accepts packets out of order (fairly easy?)
        self.filestream = open(filename, 'rb')
        self.initial_sequence_number = randint(0, 65535)
        self.load_file(self.initial_sequence_number)

        # State tracking variable:
        # 0: Transfer has not started
        # 1: Transfer is in progress
        # 2: Transfer is ending
        # 3: Transfer has ended
        self.current_state = 0

        # Main loop.
        while True:
            # state_options[self.current_state]()
            try:
                print("Current State: {0}".format(self.current_state))
                if self.current_state == 0:
                    print("Sending start packet: data size: {0}".format(sys.getsizeof(self.msg_window[0][1])))
                    # Send initial start message
                    self.send(self.make_packet('start', self.msg_window[0][0], self.msg_window[0][1]),
                              (self.dest, self.dport))
                    self.msg_window[0][2] = True
                elif self.current_state == 1:
                    # Send normal data
                    self.send_next_data()
                elif self.current_state == 2:
                    # Send the end packet last
                    self.send(self.make_packet('end', self.msg_window[0][0], self.msg_window[0][1]),
                              (self.dest, self.dport))
                    self.msg_window[0][2] = True
                else:
                    # Exit the program
                    exit()

                # Receive the message and where it came from
                message = self.receive(self.rtimeout)

                # if a message is received
                if message:
                    # Split the received packet up into it's individual parts
                    msg_type, seqno, data, checksum = self.split_packet(message)
                    print('Received message: mt: {0} sn: {1} d: {2} d(B): {3} c: {4}'.format(msg_type, seqno, data,
                                                                                             sys.getsizeof(data),
                                                                                             checksum))

                    # Try and handle the message depending on it's type
                    try:
                        # Convert the string into an int.
                        seqno = int(seqno)
                    except:
                        raise ValueError

                    # If the message contains no errors
                    if Checksum.validate_checksum(message):
                        # Handle the message using one of the methods defined by the MESSAGE_HANDLER dictionary.
                        self.MESSAGE_HANDLER.get(msg_type, self._handle_other)(seqno, data)
                    elif self.debug:
                        print("checksum failed: %s" % message)
            except (KeyboardInterrupt, SystemExit):
                exit()
            except ValueError as e:
                if self.debug:
                    print(e)
                pass
            except:
                pass

    def increment_state(self):
        self.current_state += 1

    def load_file(self, sn):
        # Read in a file and split the input file into data chunks and return data chunks.
        # The file is converted to a bytestream that reads in the file, either reading in only what is necessary and
        # putting that into the msg_window, or reading in the entire file into a 2D list where each element represents
        # a (data (bytearray), seqno (int), sent (bool)) data pair. The seqno is set here to the initial value
        # and incremented by the number of bytes in the current packet.
        current_seqno = sn
        self.filestream.seek(0)
        self.msg_window = [[current_seqno, self.filestream.read(1458),False],]
        if sys.getsizeof(self.msg_window[0][1]) == 1458:
            for var in list(range(5)):
                packet_size = sys.getsizeof(self.msg_window[var][1])
                current_seqno += packet_size
                self.msg_window.append([current_seqno, self.filestream.read(1458),False])
        else:
            # If the file is super small, may need to append an 'end' packet
            packet_size = sys.getsizeof(self.msg_window[0][1])
            current_seqno += packet_size
            self.msg_window.append([current_seqno, '',False]) # 'end' packet

    def update_sliding_window(self, sn):
        current_seqno = sn
        self.filestream.seek(current_seqno)
        next_packet = self.filestream.read(1458)
        print(os.path.getsize(filename))
        print(os.path.getsize(filename) - current_seqno)
        if (os.path.getsize(filename) - current_seqno) < 1458:
            self.msg_window = [
                [current_seqno, next_packet,False]]
        else:
            self.msg_window = [
                [current_seqno, next_packet,False],
                [current_seqno + 1, self.filestream.read(1458),False],
                [current_seqno + 2, self.filestream.read(1458),False],
                [current_seqno + 3, self.filestream.read(1458),False],
                [current_seqno + 4, self.filestream.read(1458),False]]
            
        # Check to see if this is the first packet (start)
        if self.current_state == 0:
            self.increment_state()
        # Check to see if there is only one packet left in the window
        if self.msg_window.__len__() <= 1:
            self.increment_state()
        pass

    '''
    Attempt to send the selected data packet from the sliding window and mark it as sent.
    '''
    def send_data(self, index):
        try:
            # If there is a packet to send, send it
            if self.msg_window[index]:
                self.send(self.make_packet('data', self.msg_window[index][0], self.msg_window[index][1]),
                          (self.dest, self.dport))
                # Set the sent flag for that packet in the sliding window
                self.msg_window[index][2] = True
        except:
            pass

    '''
    Send the next unsent data packet from the sliding window and mark it as sent.
    '''
    def send_next_data(self):
        # If there is still data unsent
        if len(self.msg_window) > 0:
            # Check for unsent packets
            packet_to_send = False
            i = 0
            while (not packet_to_send) and (i < len(self.msg_window)):
                if not self.msg_window[i][2]:
                    packet_to_send = True
                else:
                    i += 1
            # If there is a packet to send, send it
            if packet_to_send:
                print("Sending data packet: data size: {0} seqno: {1}".format(sys.getsizeof(self.msg_window[i][1]), self.msg_window[i][0]))
                self.send(self.make_packet('data', self.msg_window[i][0], self.msg_window[i][1]),
                      (self.dest, self.dport))
                # Set the sent flag for that packet in the sliding window
                self.msg_window[i][2] = True
        pass

    '''
    If an acknowledgement packet is received:
        If the sequence number matches a sent packet in the sliding window:
            Remove the packet from the sliding window and refresh the sliding window with another packet.
    '''
    # Handle an 'ack' reply from the server
    def _handle_ack(self, seqno, data):
        # If the seqno matches one of the packets in the sliding window
        temp_packet = []
        temp_index = 0

        for index in list(range(self.msg_window.__len__())):
            if seqno - sys.getsizeof(self.msg_window[index][1]) == self.msg_window[index][0]:
                temp_packet = self.msg_window[index]
                temp_index = index
                break

        if len(temp_packet) > 0:
            # If the packet has been sent previously, accept it
            if self.msg_window[temp_index][2]:
                # Remove the packet from the sliding window list
                del self.msg_window[temp_index]
                # Refresh the sliding window
                self.update_sliding_window()
        # if the seqno doesn't match anything in the sliding window, ignore it.
        pass


    # handler for packets with unrecognized type
    def _handle_other(self, seqno, data):
        # Not sure if anything should go here... Just ignore them... it'll be fine... I think...
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
