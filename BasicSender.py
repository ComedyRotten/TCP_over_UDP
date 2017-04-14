import random
import socket
import sys

import Checksum

'''
Modified Basic Sender
Editors: Reuben Sonnenberg and Devon Olson
This is the basic sender class. Your sender will extend this class and will
implement the start() method.
'''
class BasicSender(object):
    def __init__(self,dest,port,filename,debug=False):
        self.debug = debug
        self.dest = dest
        self.dport = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(None) # blocking
        self.sock.bind(('',random.randint(10000,40000)))
        if filename == None:
            self.infile = sys.stdin
        else:
            self.infile = open(filename,"rb")

    # Waits until packet is received to return.
    def receive(self, timeout=None):
        self.sock.settimeout(timeout)
        try:
            return self.sock.recv(4096)
        except (socket.timeout, socket.error):
            return None

    # Sends a packet to the destination address.
    def send(self, message, address=None):
        if address is None:
            address = (self.dest,self.dport)
        self.sock.sendto(message, address)

    # Prepares a packet
    def make_packet(self,msg_type=None,seqno=None,msg=None,packet=None):
        if msg_type is not None:
            body = b"".join([msg_type.encode(), b'|', bytes(str(seqno).encode()), b'|', msg, b'|'])
            checksum = Checksum.generate_checksum(body)
            return_packet = body + checksum
            return return_packet
        else:
            body = b"".join([packet[0].encode(), b'|', bytes(str(packet[1]).encode()), b'|', packet[2], b'|'])
            checksum = Checksum.generate_checksum(body)
            return_packet = body + checksum
            return return_packet


    def split_packet(self, message):
        pieces = message.split(b'|')
        msg_type, seqno = pieces[0:2]  # first two elements always treated as msg type and seqno
        checksum = pieces[-1]  # last is always treated as checksum
        data = b'|'.join(pieces[2:-1])  # everything in between is considered data
        return msg_type.decode(), int(seqno), data, checksum

    # Main sending loop.
    def start(self):
        raise NotImplementedError
