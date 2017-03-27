import getopt
import sys
from random import randint

import BasicSender


class Sender(BasicSender.BasicSender):

    def __init__(self, dest, port, filename, listenport=33122, debug=False, timeout=10):
        super().__init__(dest, port, filename, debug)
        self.rtimeout = timeout

    # Main sending loop.
    def start(self):
        while True:
            try:
                # messages = self.load_file(filename)
                self.send(self.make_packet('start',randint(0, 4096),b'Test message!'),(self.dest, self.dport))
                print("Sent message. Waiting for reply...")
                msg = self.receive(self.rtimeout)
                if msg:
                    msg_type, seqno, data, chksum  = self.split_packet(msg)
                    print("msg_type: " + msg_type + "  seqno: " + seqno + "  data: " + data + "  chksum: " + chksum)
            except (KeyboardInterrupt, SystemExit):
                exit()
            except ValueError as e:
                if self.debug:
                    print(e)
                pass # ignore

    def load_file(self,fname):
        # Read in a file and split the input file into data chunks and return data chunks.
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
