import time
import threading
try:
    import Queue as Q # For python 2
except:
    import queue as Q # For python 3
import logging
import re
import os
from userInterface import UserInterface
from sonosInterface import SonosInterface
from datetime import datetime


class UserInterfaceThread(threading.Thread):
    def __init__(self, stopper, q, reset):
        super(UserInterfaceThread, self).__init__()
        self.stopper = stopper
        self.q = q
        self.reset = reset
        self.ui = UserInterface()
        
    def run(self):
        logging.debug("UserInterfaceThread starting")
        self.ui.run(self.stopper, self.q, self.reset)
        logging.debug("UserInterfaceThread stopping")

class SonosInterfaceThread(threading.Thread):
    def __init__(self, stopper, q, shutdownPi):
        super(SonosInterfaceThread, self).__init__()
        self.stopper = stopper
        self.q = q
        self.room = "Office"
        #self.room = "Bedroom"
        self.network = "aantgr"
        self.playlistBasename = "zCharliebert"
        self.parser = re.compile("^([A-Z/]+)(\s+([A-Z]+))*(\s+([-0-9]+))*\s*$")
        self.si = SonosInterface()
        self.shutdownPi = shutdownPi
        
    def run(self):
        logging.debug("SonosInterfaceThread starting")
        try:
            while not self.stopper.is_set():
                #time.sleep(1)
                logging.debug("Sonos Interface: Waiting for a command to execute")
                command = self.q.get()
                if command is None:
                    break
                logging.debug("Sonos Interface: Obtained command {}".format(command))
                self.q.task_done()

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
                        ## Hack to work around the need for a password when using sudo:
                        ## sudo chmod u+s /sbin/shutdown
                        ## (using sleep to delay the actual shutdown, so as to leave time for the python program to quit properly)
                        #os.system("( sleep 2; /sbin/shutdown -h now ) &")
                        self.shutdownPi.set()

                        try:
                            logging.debug("Setting stopper to stop charliebert before shutting down the pi " + \
                                          "(otherwise the shutdown thread will survive for the next startup)")
                            self.stopper.set()
                        except:
                            logging.debug("Could not set stopper")

                    elif m.group(1) == "ROOM":
                        roomNb = int(m.group(5))
                        logging.debug("Command ROOM: {:d}".format(roomNb))
                        if roomNb == 1:
                            self.changeNetwork("aantgr")
                            self.room = "Bedroom"
                        elif roomNb == 2:
                            self.changeNetwork("aantgr")
                            self.room = "Bathroom"
                        elif roomNb == 3:
                            self.changeNetwork("aantgr")
                            self.room = "Office"  
                        elif roomNb == 4:
                            self.changeNetwork("aantgr")
                            self.room = "Kitchen"  
                        elif roomNb == 5:
                            self.changeNetwork("aantgr")
                            self.room = "Living Room"  
                        elif roomNb == 6:
                            self.changeNetwork("aantgr")
                            self.room = "Charlie's Room"                                                                                                                                    
                        elif roomNb == 7:
                            self.changeNetwork("AP2")
                            self.room = "Wohnzimmer"                                                                                                                                    
                        elif roomNb == 8:
                            self.changeNetwork("AP2")
                            self.room = "Obenauf"                                                                                                                                    
                        else:
                            logging.error("Command ROOM: {:d}: Room does not exist".format(roomNb))
                    else:
                       raise 
                except:
                    logging.error("Unrecognized command: '{}'".format(command))
                
        except KeyboardInterrupt:
            logging.debug("Sonos Interface stopped (Ctrl-C)")
        logging.debug("SonosInterfaceThread stopping")

    def changeNetwork(self, network):
        if network == self.network:
            return
        
        # The config file /etc/wpa_supplicant/wpa_supplicant.conf has to look like:
        #ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
        #update_config=1
        #country=GB
        #
        #network={
        #    ssid="aantgr"
        #    psk="********"
        #    key_mgmt=WPA-PSK
        #    priority=10
        #}
        #network={
        #    ssid="AP2"
        #    psk="********"
        #    key_mgmt=WPA-PSK
        #    priority=1
        #}

        if network == "aantgr":
            os.system("wpa_cli select_network 0")
        elif network == "AP2":
            os.system("wpa_cli select_network 1")
        else:
            logging.error("Unknown network '{}'".format(network))
            return
        
        time.sleep(5)
        
        self.network = network
        
# # Function that sends a shutdown command after a period of inactivity
# def sendShutdownSignal():
#     logging.debug("No activity for {} seconds: Sending signal to shut down the pi".format(self.shutdownTimePeriod))
#     logging.debug("   [Start time: {}]".format(self.startTime))
# 
#     if self.queue is not None:
#         try:
#             self.queue.put("SHUTDOWN")
#         except:
#             logging.debug("Problem while sending the shutdown signal")
#         
# # Reset the shutdown timer with each new key press
# def setShutdownTimer(shutdownTimer, stopper):
#     if stopper.is_set():
#         logging.debug("Refusing to set a shutdown timer since we are quitting")
#         return
#     
#     try:
#         logging.debug("Starting timer to shut down the pi when inactive for {} seconds".format(self.shutdownTimePeriod))
#         # Cancel current timer if applicable
#         try:
#             if shutdownTimer is None:
#                 logging.debug("Setting the timer for the first time")
#             else:
#                 logging.debug("Resetting the timer")
#                 shutdownTimer.cancel()
#         except:
#             pass
#         # (Re)Start timer to monitor inactivity after the last key press
#         shutdownTimer = threading.Timer(shutdownTimePeriod, sendShutdownSignal)
#         shutdownTimer.setName("ShutdownTimer")
#         shutdownTimer.start()
#     except:
#         logging.error("Problem encountered when trying to (re)set the shutdown timer")
#             
class ShutdownTimerThread(threading.Thread):
    def __init__(self, stopper, reset, shutdownFlag, startTime):
        super(ShutdownTimerThread, self).__init__()
        self.stopper = stopper
        self.reset = reset
        self.shutdownFlag = shutdownFlag
        self.startTime = startTime
        #self.shutdownTimePeriod = 1800 # s
        self.shutdownTimePeriod = 120 # s
        
    def run(self):
        logging.debug("ShutdownTimerThread starting")
        while not self.stopper.is_set():
            while not self.reset.wait(self.shutdownTimePeriod):
                if not self.stopper.is_set():
                    logging.debug("ShutdownTimerThread: Setting flag to shut down the Pi")
                    logging.debug("Original start time: {}".format(self.startTime))
                    self.shutdownFlag.set()
                    self.stopper.set()
                
            if self.reset.is_set() and not self.stopper.is_set():
                logging.debug("ShutdownTimerThread: Resetting the shutdown timer")
                self.reset.clear()

        logging.debug("ShutdownTimerThread stopping")
        
        
            
def charliebert():
    # State indicator
    stopper = threading.Event()
    # Queue for commands
    q = Q.Queue()
    #
    shutdownPi = threading.Event()
    reset = threading.Event()
    startTime = "charliebert start: {}".format(datetime.now())
    logging.debug("{}".format(self.startTime))
    
    userInterfaceThread = UserInterfaceThread(stopper, q, reset)
    sonosInterfaceThread = SonosInterfaceThread(stopper, q, shutdownPi)

    shutdownTimerThread = ShutdownTimerThread(stopper, reset, shutdownPi, startTime)
    
    logging.debug("Starting userInterfaceThread thread")
    userInterfaceThread.start()
    logging.debug("Starting sonosInterfaceThread thread")
    sonosInterfaceThread.start()

    logging.debug("Starting shutdownTimerThread thread")
    shutdownTimerThread.start()
    
    # File acting as a switch for this application:
    switchFile = "CHARLIEBERT_STOP"
    if os.path.exists(switchFile):
        logging.debug("Removing switch file CHARLIEBERT_STOP")
        os.remove(switchFile)
    
#     # Timer to trigger a shutdown after a given period of inactivity
#     #shutdownTimePeriod = 1800 # s
#     shutdownTimePeriod = 600 # s
#     shutdownTimer = None
#     startTime = time.asctime( time.localtime(time.time()) )
#     
#     logging.info("Starting timer to monitor activity and shut down the pi after a given idle time") 
#     setShutdownTimer(shutdownTimer, stopper)
            
    try:
        while not os.path.exists(switchFile) and not stopper.is_set():
            pass
        
        if os.path.exists(switchFile):
            logging.debug("Stop requested using the flag file '{}'".format(switchFile))
            os.remove(switchFile)

           
    except KeyboardInterrupt:
        logging.debug("Stop requested")
        stopper.set() 
        reset.set() 
    
    finally:
        if not stopper.is_set():
            stopper.set() 
        if not reset.is_set():
            reset.set() 
            
#         logging.debug("Canceling shutdown timer")
#         try:
#             self.shutdownTimer.cancel()
#         except:
#             pass
            
        while not q.empty():
            q.get()
        q.put(None)
        
    if shutdownPi.is_set():
        logging.debug("Shutting down Pi now")
        # Hack to work around the need for a password when using sudo:
        # sudo chmod u+s /sbin/shutdown
        # (using sleep to delay the actual shutdown, so as to leave time for the python program to quit properly)
        #logging.debug("/sbin/shutdown -h now")
        os.system("/sbin/shutdown -h now")
            

if __name__ == '__main__':
    # Logging
    logging.basicConfig(filename='charliebert.log', 
                        level=logging.DEBUG, 
                        format='%(asctime)s %(name)s %(levelname)s:%(message)s', 
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger("soco").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
        
    logging.info("Starting charliebert")             
    charliebert()
    logging.info("Quitting charliebert")
