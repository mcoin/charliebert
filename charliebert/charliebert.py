import time
import threading
import logging
#import os
#import sys
from userInterface import UserInterface


class UserInterfaceThread(threading.Thread):
    def __init__(self, stopper, command):
        super(UserInterfaceThread, self).__init__()
        self.stopper = stopper
        self.command = command
        self.ui = UserInterface()
        
    def run(self):
        logging.debug("UserInterfaceThread starting")
        self.ui.run(self.stopper, self.command)
        logging.debug("UserInterfaceThread stopping")

class SonosInterfaceThread(threading.Thread):
    def __init__(self, stopper, command):
        super(SonosInterfaceThread, self).__init__()
        self.stopper = stopper
        self.command = command
        
    def run(self):
        logging.debug("SonosInterfaceThread starting")
        try:
            while not self.stopper.is_set():
                #time.sleep(1)
                logging.debug("Sonos Interface: Waiting for a command to execute")
                self.command.wait()
                if self.stopper.is_set():
                    break
                
                logging.debug("Sonos Interface: Obtained command")
                
        except KeyboardInterrupt:
            logging.debug("Sonos Interface stopped (Ctrl-C)")
        logging.debug("SonosInterfaceThread stopping")

def charliebert():
    # State indicator
    stopper = threading.Event()
    # Signal for a new command to execute
    command = threading.Event()
    
    userInterfaceThread = UserInterfaceThread(stopper, command)
    sonosInterfaceThread = SonosInterfaceThread(stopper, command)

    
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
        command.set()
            

if __name__ == '__main__':
    # Logging
    logging.basicConfig(filename='charliebert.log', 
                        level=logging.DEBUG, 
                        format='%(asctime)s %(levelname)s:%(message)s', 
                        datefmt='%Y-%m-%d %H:%M:%S')
        
    logging.info("Starting charliebert")             
    charliebert()
    logging.info("Quitting charliebert")
