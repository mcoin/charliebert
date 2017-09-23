import time
import threading
import logging
#import os
#import sys
from userInterface import UserInterface


class UserInterfaceThread(threading.Thread):
    def __init__(self, stopper):
        super(UserInterfaceThread, self).__init__()
        self.stopper = stopper
        self.ui = UserInterface()
        
    def run(self):
        logging.debug("UserInterfaceThread starting")
        self.ui.run(self.stopper)
        logging.debug("UserInterfaceThread stopping")

class SonosInterfaceThread(threading.Thread):
    def __init__(self, stopper):
        super(SonosInterfaceThread, self).__init__()
        self.stopper = stopper
        
    def run(self):
        logging.debug("SonosInterfaceThread starting")
        try:
            while not self.stopper.is_set():
                time.sleep(1)
                logging.debug("Sonos Interface")
        except KeyboardInterrupt:
            logging.debug("Sonos Interface stopped (Ctrl-C)")
        logging.debug("SonosInterfaceThread stopping")

def charliebert():
    # State indicator
    stopper = threading.Event()
    
    userInterfaceThread = UserInterfaceThread(stopper)
    sonosInterfaceThread = SonosInterfaceThread(stopper)

    
    logging.debug("Starting userInterfaceThread thread")
    userInterfaceThread.start()
    logging.debug("Starting sonosInterfaceThread thread")
    sonosInterfaceThread.start()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        logging.debug("Stop requested")
        stopper.set()
            

if __name__ == '__main__':
    # Logging
    logging.basicConfig(filename='charliebert.log', 
                        level=logging.DEBUG, 
                        format='%(asctime)s %(levelname)s:%(message)s', 
                        datefmt='%Y-%m-%d %H:%M:%S')
        
    logging.info("Starting charliebert")             
    charliebert()
    logging.info("Quitting charliebert")
