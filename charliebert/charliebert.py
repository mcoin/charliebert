import time
import threading
import Queue
import logging
import re
import os
from userInterface import UserInterface
from sonosInterface import SonosInterface


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
        self.room = "Office"
        #self.room = "Bedroom"
        self.playlistBasename = "zCharliebert"
        self.parser = re.compile("^([A-Z/]+)(\s+([A-Z]+))*(\s+([-0-9]+))*\s*$")
        self.si = SonosInterface()
        
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

                # Process commands using the following mini-parser: 'CMD [BANK] [VALUE]'
                m = self.parser.match(command)
                try:
                    if m.group(1) == "PLAY/PAUSE":
                        logging.debug("Command PLAY/PAUSE")
                        self.si.togglePlayPause(self.room)
                    elif m.group(1) == "FORWARD":
                        logging.debug("Command FORWARD")
                        self.si.skipToNext(self.room)
                    elif m.group(1) == "BACK":
                        logging.debug("Command BACK")
                        self.si.skipToPrevious(self.room)
                    elif m.group(1) == "PLAYLIST":
                        bank = m.group(3)
                        bankNb = int(m.group(5))
                        logging.debug("Command PLAYLIST: {} {:d}".format(bank, bankNb))
                        playlistName = "{0}_{1}{2:02d}".format(self.playlistBasename, bank, bankNb)
                        logging.debug("Starting playlist {}".format(playlistName))
                        self.si.startPlaylist(playlistName, self.room)
                    elif m.group(1) == "TRACK":
                        trackNb = int(m.group(5))
                        logging.debug("Command TRACK: {:d}".format(trackNb))
                        self.si.playTrackNb(trackNb, self.room)
                    elif m.group(1) == "VOLUME":
                        volDelta = int(m.group(5))
                        logging.debug("Command VOLUME: {:d}".format(volDelta))
                        self.si.adjustVolume(volDelta, self.room)
                    elif m.group(1) == "SHUTDOWN":
                        logging.debug("Command SHUTDOWN")
                        # Hack to work around the need for a password when using sudo:
                        # sudo chmod u+s /sbin/shutdown
                        os.system("/sbin/shutdown -h now")
                    else:
                       raise 
                except:
                    logging.error("Unrecognized command: '{}'".format(command))
                
        except KeyboardInterrupt:
            logging.debug("Sonos Interface stopped (Ctrl-C)")
        logging.debug("SonosInterfaceThread stopping")

def charliebert():
    # State indicator
    stopper = threading.Event()
    # Queue for commands
    queue = Queue.Queue()
    
    
    userInterfaceThread = UserInterfaceThread(stopper, queue)
    sonosInterfaceThread = SonosInterfaceThread(stopper, queue)

    
    logging.debug("Starting userInterfaceThread thread")
    userInterfaceThread.start()
    logging.debug("Starting sonosInterfaceThread thread")
    sonosInterfaceThread.start()

    # File acting as a switch for this application:
    switchFile = "CHARLIEBERT_STOP"
    if os.path.exists(switchFile):
        os.remove(switchFile)
    
    try:
        while not os.path.exists(switchFile):
            pass
        
        if os.path.exists(switchFile):
            logging.debug("Stop requested using the flag file '{}'".format(switchFile))
            os.remove(switchFile)

           
    except KeyboardInterrupt:
        logging.debug("Stop requested")
    
    finally:
        stopper.set() 
        while not queue.empty():
            queue.get()
        queue.put(None)
            

if __name__ == '__main__':
    # Logging
    logging.basicConfig(filename='charliebert.log', 
                        level=logging.DEBUG, 
                        format='%(asctime)s %(name)s %(levelname)s:%(message)s', 
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger("soco").setLevel(logging.WARNING)
        
    logging.info("Starting charliebert")             
    charliebert()
    logging.info("Quitting charliebert")
