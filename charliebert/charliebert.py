import time
import threading
import logging
#import os
#import sys
from userInterface import UserInterface


class UserInterfaceThread(threading.Thread):
    def __init__(self, stopper, queue):
        super(UserInterfaceThread, self).__init__()
        self.stopper = stopper
        self.queue = queue
        self.ui = UserInterface()
        
    def run(self):
        logging.debug("UserInterfaceThread starting")
        self.ui.run(self.stopper, self.queue)
        logging.debug("UserInterfaceThread stopping")

class SonosInterfaceThread(threading.Thread):
    def __init__(self, stopper, queue):
        super(SonosInterfaceThread, self).__init__()
        self.stopper = stopper
        self.queue = queue
        
    def run(self):
        logging.debug("SonosInterfaceThread starting")
        try:
            while not self.stopper.is_set():
                #time.sleep(1)
                logging.debug("Sonos Interface: Waiting for a command to execute")
                command = self.queue.get()
                if command is None:
                    break
                logging.debug("Sonos Interface: Obtained command {}".format(command))
                self.queue.task_done()

                #self.command.wait()
                #if self.stopper.is_set():
                #    break
                #
                #logging.debug("Sonos Interface: Obtained command")
                #self.command.clear()
                
        except KeyboardInterrupt:
            logging.debug("Sonos Interface stopped (Ctrl-C)")
        logging.debug("SonosInterfaceThread stopping")

def charliebert():
    # State indicator
    stopper = threading.Event()
    # Queue for commands
    queue = queue.Queue()
    
    
    userInterfaceThread = UserInterfaceThread(stopper, queue)
    sonosInterfaceThread = SonosInterfaceThread(stopper, queue)

    
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
                        format='%(asctime)s %(name)s %(levelname)s:%(message)s', 
                        datefmt='%Y-%m-%d %H:%M:%S')
        
    logging.info("Starting charliebert")             
    charliebert()
    logging.info("Quitting charliebert")
