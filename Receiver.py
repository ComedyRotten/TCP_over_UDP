import getopt
import socket
import sys
import time

import Checksum

'''
Modified Receiver
Editors: Reuben Sonnenberg and Devon Olson
The "ack" and "handle..." methods were modified most.
'''

class Connection():
    def __init__(self,host,port,start_seq,filename,debug=False):
        self.debug = debug
        self.updated = time.time()
        self.current_seqno = start_seq # expect to ack from the start_seqno
        self.host = host
        self.port = port
        self.max_buf_size = 5
        self.outfile = open("out_{0}".format(filename),"wb")
        self.seqnums = {} # enforce single instance of each seqno

    def ack(self,seqno, data):
        res_data = []
        self.updated = time.time()
        # if the sequence number of the received packet is larger than the current sequence number and
        # the window size is not exceeded
        if (seqno == self.current_seqno) and self.seqnums.__len__() <= self.max_buf_size:
            # Add the data to the window with the sequence number as the lookup value
            self.seqnums[seqno] = data
            # Then, for every sequence number
            for n in sorted(self.seqnums.keys()):
                # If the sequence number is equal to the one we need
                if n == self.current_seqno:
                    # "Receive" and rebuild the data and remove if from the window
                    self.current_seqno += len(data)
                    res_data.append(self.seqnums[n])
                    del self.seqnums[n]
                else:
                    break # when we find out of order seqno, quit and move on

        if self.debug:
            print("next seqno should be %d" % (self.current_seqno))

        # note: we return the sequence number of the last packet received
        return (self.current_seqno - len(data)), res_data

    def record(self,data):
        self.outfile.write(data)
        self.outfile.flush()

    def end(self):
        self.outfile.close()

class Receiver():
    def __init__(self,listenport=33122,debug=False,timeout=10):
        self.debug = debug
        self.timeout = timeout
        self.last_cleanup = time.time()
        self.port = listenport
        self.host = ''
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.settimeout(timeout)
        self.s.bind((self.host,self.port))
        self.connections = {} # schema is {(address, port) : Connection}
        self.MESSAGE_HANDLER = {
            'start' : self._handle_start,
            'data' : self._handle_data,
            'end' : self._handle_end,
            'ack' : self._handle_ack
        }

    def start(self):
        while True:
            try:
                # Receive the message and where it came from
                message, address = self.receive()
                # Split the message up into it's appropriate parts
                msg_type, seqno, data, checksum = self._split_message(message)
                if debug:
                    print('Received message: {0} {1} {2} {3} {4}'.format(msg_type, seqno, data, sys.getsizeof(data), checksum))
                if Checksum.validate_checksum(message):
                    # If the checksum checks out, handle the message using one of the following methods defined by the
                    # MESSAGE_HANDLER dictionary.
                    self.MESSAGE_HANDLER.get(msg_type,self._handle_other)(seqno, data, address)
                elif self.debug:
                    print("checksum failed: %s" % message)

                # If the timeout happens, do a cleanup.
                if time.time() - self.last_cleanup > self.timeout:
                    self._cleanup()
            except socket.timeout:
                self._cleanup()
            except (KeyboardInterrupt, SystemExit):
                exit()
            except ValueError as e:
                if self.debug:
                    print(e)
                pass # ignore

    # waits until packet is received to return
    def receive(self):
        return self.s.recvfrom(4096)

    # sends a message to the specified address. Addresses are in the format:
    #   (IP address, port number)
    def send(self, message, address):
        self.s.sendto(message, address)

    # this sends an ack message to address with specified seqno
    def _send_ack(self, seqno, address):
        m = b"".join([b'ack|', bytes(str(seqno).encode()), b'|'])
        checksum = Checksum.generate_checksum(m)
        #message = "%s%s" % (m, checksum)
        message = m + checksum
        self.send(message, address)

    def _handle_start(self, seqno, data, address):
        if not address in self.connections:
            self.connections[address] = Connection(address[0],address[1],seqno,data.decode(),self.debug)
        conn = self.connections[address]
        ackno, res_data = conn.ack(seqno,data)
        for l in res_data:
            if self.debug:
                print(data)
        self._send_ack(ackno, address)

    # ignore packets from uninitiated connections
    def _handle_data(self, seqno, data, address):
        if address in self.connections:
            conn = self.connections[address]
            ackno,res_data = conn.ack(seqno,data)
            for l in res_data:
                if self.debug:
                    print(l)
                conn.record(l)
            self._send_ack(ackno, address)

    # handle end packets
    def _handle_end(self, seqno, data, address):
        if address in self.connections:
            conn = self.connections[address]
            ackno, res_data = conn.ack(seqno,data)
            for l in res_data:
                if self.debug:
                    print(l)
                conn.record(l)
            self._send_ack(ackno, address)

    # I'll do the ack-ing here, buddy
    def _handle_ack(self, seqno, data, address):
        pass

    # handler for packets with unrecognized type
    def _handle_other(self, seqno, data, address):
        pass

    def _split_message(self, message):
        pieces = message.split(b'|')
        msg_type, seqno = pieces[0:2]  # first two elements always treated as msg type and seqno
        checksum = pieces[-1]  # last is always treated as checksum
        data = b'|'.join(pieces[2:-1])  # everything in between is considered data
        return msg_type.decode(), int(seqno), data, checksum

    def _cleanup(self):
        if self.debug:
            print("clean up time")
        now = time.time()
        for address in list(self.connections):
            conn = self.connections[address]
            if now - conn.updated > self.timeout:
                if self.debug:
                    print("killed connection to %s (%.2f old)" % (address, now - conn.updated))
                conn.end()
                del self.connections[address]
        self.last_cleanup = now

if __name__ == "__main__":
    def usage():
        print("BEARS-TP Receiver")
        print("-p PORT | --port=PORT The listen port, defaults to 33122")
        print("-t TIMEOUT | --timeout=TIMEOUT Receiver timeout in seconds")
        print("-d | --debug Print debug messages")
        print("-h | --help Print this usage message")

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                               "p:dt:", ["port=", "debug=", "timeout="])
    except:
        usage()
        exit()

    port = 33122
    debug = False
    timeout = 10

    for o,a in opts:
        if o in ("-p", "--port="):
            port = int(a)
        elif o in ("-t", "--timeout="):
            timeout = int(a)
        elif o in ("-d", "--debug="):
            debug = True
        else:
            print(usage())
            exit()
    r = Receiver(port, debug, timeout)
    r.start()
