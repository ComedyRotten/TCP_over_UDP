import getopt
import os
import sys
from random import randint

import BasicSender
import Checksum

'''
Extended Sender
Editors: Reuben Sonnenberg and Devon Olson
'''

class Sender(BasicSender.BasicSender):

    def __init__(self, dest, port, filename, listenport=33122, debug=False, timeout=10):
        super().__init__(dest, port, filename, debug)
        self.rtimeout = timeout
        self.filename = filename
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
        self.initial_sn = randint(0, 65535)
        self.current_sn = self.initial_sn
        self.msg_window = []
        self.filesize = 0
        self.load_file()

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
                if self.current_state == 0:
                    # Send initial start message
                    # msgtype|seqno|data|checksum
                    self.send(self.make_packet('start', self.msg_window[0][0], self.msg_window[0][1]),
                              (self.dest, self.dport))
                    self.msg_window[0][2] = True
                elif self.current_state == 1:
                    # Send unacknowledged packets
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
                    # If the message contains no errors
                    if Checksum.validate_checksum(message):
                        # Handle the message using one of the methods defined by the MESSAGE_HANDLER dictionary.
                        self.MESSAGE_HANDLER.get(msg_type, self._handle_other)(seqno, data)
                    elif self.debug:
                        print("checksum failed: %s" % message)
                else:
                    pass
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

    def load_file(self):
        # Read in a file and split the input file into data chunks and return data chunks.
        # The file is converted to a bytestream that reads in the file, either reading in only what is necessary and
        # putting that into the msg_window, or reading in the entire file into a 2D list where each element represents
        # a (data (bytearray), seqno (int), sent (bool)) data pair. The seqno is set here to the initial value
        # and incremented by the number of bytes in the current packet.

        # create the first packet, reset the initial sn so that things are in order from now on
        self.msg_window.append([self.current_sn, self.filename.encode('utf-8'), False])
        self.initial_sn += len(self.filename.encode('utf-8'))
        self.current_sn = self.initial_sn

        with open(self.filename, 'rb') as sending_file:
            self.filesize = os.stat(self.filename).st_size

            # if the window is not full, and there is still more data in the file to retrieve
            while ((self.msg_window.__len__() < 5) and (self.filesize > (self.current_sn - self.initial_sn))):
                sending_file.seek(self.current_sn - self.initial_sn)
                next_packet = sending_file.read(1458)
                self.msg_window.append([self.current_sn, next_packet, False])
                self.current_sn += len(next_packet)
    
            if self.msg_window.__len__() < 5:
                # If the file is super small, may need to append an 'end' packet in this step
                packet_size = len(self.msg_window[self.msg_window.__len__() - 1][1])
                self.current_sn += packet_size
                self.msg_window.append([self.current_sn, '',False]) # 'end' packet

    def update_sliding_window(self):
        with open(self.filename, 'rb') as sending_file:
            # check to see if the window is full
            if self.msg_window.__len__() < 5:
                # if the window is not full, and there is still more data in the file to retrieve
                while ((self.msg_window.__len__() < 5) and
                           (self.filesize > (self.current_sn - self.initial_sn))):
                    sending_file.seek(self.current_sn - self.initial_sn)
                    next_packet = sending_file.read(1458)
                    self.msg_window.append([self.current_sn, next_packet, False])
                    self.current_sn += len(next_packet)
            else:
                # If the window does not need updated, keep running...
                pass

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
    def resend_data(self):
        try:
            i = 0
            while (i < len(self.msg_window)):
                # If there is a packet to send, send it
                if self.msg_window[i]:
                    self.send(self.make_packet('data', self.msg_window[i][0], self.msg_window[i][1]),
                              (self.dest, self.dport))
                    # Set the sent flag for that packet in the sliding window
                    self.msg_window[i][2] = True
                i += 1
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

            # If there are packets to send, start with the previous unsent packets and send them
            if packet_to_send:
                while (i < len(self.msg_window)):
                    self.send(self.make_packet('data', self.msg_window[i][0], self.msg_window[i][1]),
                              (self.dest, self.dport))
                    # Set the sent flag for that packet in the sliding window
                    self.msg_window[i][2] = True
                    i += 1
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
            if seqno == self.msg_window[index][0]:
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
