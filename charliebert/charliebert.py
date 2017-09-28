import time
import threading
import Queue
import logging
import re
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
        self.room = "Office"
        self.playlistBasename = "zCharliebert"
        
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

                # Process commands
                if re.search("^PLAY/PAUSE$", command):
                    logging.debug("Command PLAY/PAUSE")
                    si.togglePlayPause(self.room)
                elif re.search("^FORWARD$", command):
                    logging.debug("Command FORWARD")
                    si.skipToNext(self.room)
                elif re.search("^BACK$", command):
                    logging.debug("Command BACK")
                    si.skipToPrevious(self.room)
                elif re.search("^PLAYLIST\s+([A-Z])\s+([0-9]+)\s*$", command):
                    m = re.search("^PLAYLIST\s+([A-Z])\s+([0-9]+)\s*$", command)
                    logging.debug("Command PLAYLIST: {} {:d}".format(m.group(1, 2)))
                    playlistName = "{}_{}{0:02d}".format(self.playlistBasename, m.group(1), m.group(2))
                    logging.debug("Starting playlist {}".format(playlistName))
                    si.startPlaylist(playlistName, self.room)
                elif re.search("^TRACK\s+([0-9]+)\s*$", command):
                    m = re.search("^TRACK\s+([0-9]+)\s*$", command)
                    logging.debug("Command TRACK: {:d}".format(m.group(1)))
                    si.playTrackNb(m.group(1), self.room)
                elif re.search("^VOLUME\s+([0-9]+)\s*$", command):
                    m = re.search("^VOLUME\s+([0-9]+)\s*$", command)
                    logging.debug("Command VOLUME: {:d}".format(m.group(1)))
                    si.adjustVolume(m.group(1), self.room)
                else:
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

    try:
        while True:
            pass
    except KeyboardInterrupt:
        logging.debug("Stop requested")
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
        
    logging.info("Starting charliebert")             
    charliebert()
    logging.info("Quitting charliebert")
