import time
import threading
try:
    import Queue as Q # For python 2
except:
    import queue as Q # For python 3
import logging
from logging.handlers import RotatingFileHandler
import re
import os
from userInterface import UserInterface
from sonosInterface import SonosInterface
from mpdInterface import MpdInterface
from datetime import datetime
import configparser


configFileName = 'charliebert.config'

class UserInterfaceThread(threading.Thread):
    def __init__(self, stopper, q, reset, logger, config):
        super(UserInterfaceThread, self).__init__()
        self.config = config
        self.stopper = stopper
        self.q = q
        self.reset = reset
        self.logger = logger

        self.ui = UserInterface(self.logger)
        
    def run(self):
        self.logger.debug("UserInterfaceThread starting")
        self.ui.run(self.stopper, self.q, self.reset)
        self.logger.debug("UserInterfaceThread stopping")

class PlayerInterfaceThread(threading.Thread):
    def __init__(self, stopper, q, shutdownPi, logger, config):
        super(PlayerInterfaceThread, self).__init__()
        self.config = config        
        self.stopper = stopper
        self.q = q
        
        self.availableRooms = ('Bedroom', 
                               'Bathroom', 
                               'Office', 
                               'Kitchen', 
                               'Living Room', 
                               'Charlie\'s Room', 
                               'Wohnzimmer', 
                               'Obenauf',
                               'Charliebert')
        self.room = "Office"
        #self.room = "Bedroom"
        self.availableNetworks = ('aantgr', 'AP2')
        self.network = "aantgr"
        self.availablePlaylistBasenames = "zCharliebert"
        self.playlistBasename = "zCharliebert"
        self.availablePlayers = ('Sonos', 'Mpd')
        self.player = "Sonos"
        
        self.readConfig()
        
        self.parser = re.compile("^([A-Z/]+)(\s+([A-Z]+))*(\s+([-0-9]+))*\s*$")
        self.shutdownPi = shutdownPi
        self.logger = logger

        self.si = SonosInterface(self.logger)
        self.mi = MpdInterface(self.logger)

        if self.player == 'Sonos':        
            self.pi = self.si
        else:
            self.pi = self.mi

    def readConfig(self):
        try:
            if self.config['PlayerInterface']['room'] in self.availableRooms:
                self.room = self.config['PlayerInterface']['room']
            else:
                self.logger.error("Unrecognized room from config: {}".format(self.config['PlayerInterface']['room']))
        except:
            self.logger.error("Problem encountered when attempting to set room from config")
            
        try:
            if self.config['PlayerInterface']['network'] is None:
                self.logger.debug("No network defined in config")
            else:
                if self.config['PlayerInterface']['network'] in self.availableNetworks:
                    self.network = self.config['PlayerInterface']['network']
                else:
                    self.logger.error("Unrecognized network from config: {}".format(self.config['PlayerInterface']['network']))
        except:
            self.logger.error("Problem encountered when attempting to set network from config")

        try:
            if self.config['PlayerInterface']['playlistBasename'] in self.availablePlaylistBasenames:
                self.playlistBasename = self.config['PlayerInterface']['playlistBasename']
            else:
                self.logger.error("Unrecognized playlist basename from config: {}".format(self.config['PlayerInterface']['playlistBasename']))
        except:
            self.logger.error("Problem encountered when attempting to set playlist basename from config")

        try:
            if self.config['PlayerInterface']['player'] in self.availablePlayers:
                self.player = self.config['PlayerInterface']['player']
            else:
                self.logger.error("Unrecognized player from config: {}".format(self.config['PlayerInterface']['player']))
        except:
            self.logger.error("Problem encountered when attempting to set player from config")
                    
    def run(self):
        self.logger.debug("PlayerInterfaceThread starting")
        try:
            while not self.stopper.is_set():
                #time.sleep(1)
                self.logger.debug("Sonos Interface: Waiting for a command to execute")
                command = self.q.get()
                if command is None:
                    break
                self.logger.debug("Sonos Interface: Obtained command {}".format(command))
                self.q.task_done()

                # Process commands using the following mini-parser: 'CMD [BANK] [VALUE]'
                m = self.parser.match(command)
                try:
                    if m.group(1) == "PLAY/PAUSE":
                        self.logger.debug("Command PLAY/PAUSE")
                        self.pi.togglePlayPause(self.room)
                    elif m.group(1) == "FORWARD":
                        self.logger.debug("Command FORWARD")
                        self.pi.skipToNext(self.room)
                    elif m.group(1) == "BACK":
                        self.logger.debug("Command BACK")
                        self.pi.skipToPrevious(self.room)
                    elif m.group(1) == "PLAYLIST":
                        bank = m.group(3)
                        bankNb = int(m.group(5))
                        self.logger.debug("Command PLAYLIST: {} {:d}".format(bank, bankNb))
                        playlistName = "{0}_{1}{2:02d}".format(self.playlistBasename, bank, bankNb)
                        self.logger.debug("Starting playlist {}".format(playlistName))
                        self.pi.startPlaylist(playlistName, self.room)
                    elif m.group(1) == "TRACK":
                        trackNb = int(m.group(5))
                        self.logger.debug("Command TRACK: {:d}".format(trackNb))
                        self.pi.playTrackNb(trackNb, self.room)
                    elif m.group(1) == "VOLUME":
                        volDelta = int(m.group(5))
                        self.logger.debug("Command VOLUME: {:d}".format(volDelta))
                        self.pi.adjustVolume(volDelta, self.room)
                    elif m.group(1) == "SHUTDOWN":
                        self.logger.debug("Command SHUTDOWN")
                        ## Hack to work around the need for a password when using sudo:
                        ## sudo chmod u+s /sbin/shutdown
                        ## (using sleep to delay the actual shutdown, so as to leave time for the python program to quit properly)
                        #os.system("( sleep 2; /sbin/shutdown -h now ) &")
                        self.shutdownPi.set()

                        try:
                            self.logger.debug("Setting stopper to stop charliebert before shutting down the pi " + \
                                          "(otherwise the shutdown thread will survive for the next startup)")
                            self.stopper.set()
                        except:
                            self.logger.debug("Could not set stopper")

                    elif m.group(1) == "ROOM":
                        roomNb = int(m.group(5))
                        self.logger.debug("Command ROOM: {:d}".format(roomNb))


                        if roomNb == 12:
                            if self.player != "Mpd":
                                self.player = "Mpd"
                                self.logger.debug("Switching player to MPD")
                                self.pi = self.mi
                        else:
                            if self.player != "Sonos":
                                self.player = "Sonos"
                                self.logger.debug("Switching player to Sonos")
                                self.pi = self.si

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
                        elif roomNb == 10:
                            self.changeNetwork("aapx")
                            self.room = "none"                                                                                                                                    
                        elif roomNb == 12:
                            self.room = "Charliebert"

                        else:
                            self.logger.error("Command ROOM: {:d}: Room does not exist".format(roomNb))
                    else:
                       raise 
                except:
                    self.logger.error("Unrecognized command: '{}'".format(command))
                
        except KeyboardInterrupt:
            self.logger.debug("Sonos Interface stopped (Ctrl-C)")
        self.logger.debug("PlayerInterfaceThread stopping")

    def changeNetwork(self, network):
        self.logger.debug("Changing network to '{}'".format(network))
        if network == self.network:
            self.logger.error("Network '{}' is already the active network".format(network))
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
        elif network == "aapx":
            os.system("wpa_cli select_network 2")
        else:
            self.logger.error("Unknown network '{}'".format(network))
            return
        
        time.sleep(5)
        
        self.network = network
        

# Timer to trigger a shutdown after a given period of inactivity
class ShutdownTimerThread(threading.Thread):
    def __init__(self, stopper, reset, shutdownFlag, startTime, logger):
        super(ShutdownTimerThread, self).__init__()
        self.stopper = stopper
        self.reset = reset
        self.shutdownFlag = shutdownFlag
        self.startTime = startTime
        self.logger = logger
        #self.shutdownTimePeriod = 1800 # s
        self.shutdownTimePeriod = 600 # s
        
    def run(self):
        self.logger.debug("ShutdownTimerThread starting")
        while not self.stopper.is_set():
            while not self.reset.wait(self.shutdownTimePeriod):
                if not self.stopper.is_set():
                    self.logger.debug("ShutdownTimerThread: Setting flag to shut down the Pi")
                    self.logger.debug("Original start time: {}".format(self.startTime))
                    self.shutdownFlag.set()
                    self.stopper.set()
                
            if self.reset.is_set() and not self.stopper.is_set():
                self.logger.debug("ShutdownTimerThread: Resetting the shutdown timer")
                self.reset.clear()

        self.logger.debug("ShutdownTimerThread stopping")
        
# Variant that does not rely on the "hardware" clock
class ShutdownTimerThreadWorkaround(ShutdownTimerThread):
    def __init__(self, stopper, reset, shutdownFlag, startTime, logger):
        super(ShutdownTimerThreadWorkaround, self).__init__(stopper, reset, shutdownFlag, startTime, logger)
        self.time = 0
        self.timeInterval = 5
        
    def run(self):
        self.logger.debug("ShutdownTimerThreadWorkaround starting")
        while not self.stopper.is_set():
            self.reset.clear()
            while self.time < self.shutdownTimePeriod:
                #time.sleep(self.timeInterval)
                self.stopper.wait(self.timeInterval)
                self.time += self.timeInterval
                
                if self.reset.is_set():
                    self.logger.debug("ShutdownTimerThreadWorkaround: Resetting the shutdown timer")
                    self.time = 0
                    break
                
            if not self.reset.is_set():
                self.logger.debug("ShutdownTimerThreadWorkaround: Setting flag to shut down the Pi")
                self.shutdownFlag.set()
                self.stopper.set()
                

def initConfig(logger, config):
    logger.debug("Setting initial config")
    config['Settings'] = {'Setting1': '45',
                      'Setting2': 'yes',
                      'Setting3': '9'}
    
    config['PlayerInterface'] = {'room': 'Office',
        'network': 'aantgr',
        'playlistBasename': 'zCharliebert',
        'player': 'sonos'}

def loadConfig(logger, config):
    logger.debug("Reading config from file")
    try:
        config.read(configFileName)
    except:
        logger.error("Failed to read config")
        
def writeConfig(logger, config):
    logger.debug("Writing config to file")
    with open(configFileName, 'w') as configFile:
        config.write(configFile)

            
def charliebert(logger, config):
    # Get configuration from config file if present
    loadConfig(logger, config)
    
    # State indicator
    stopper = threading.Event()
    # Queue for commands
    q = Q.Queue()
    #
    shutdownPi = threading.Event()
    reset = threading.Event()
    startTime = "charliebert start: {}".format(datetime.now())
    logger.debug("{}".format(startTime))
    
    userInterfaceThread = UserInterfaceThread(stopper, q, reset, logger, config)
    playerInterfaceThread = PlayerInterfaceThread(stopper, q, shutdownPi, logger, config)

    #shutdownTimerThread = ShutdownTimerThread(stopper, reset, shutdownPi, startTime, logger)
    shutdownTimerThread = ShutdownTimerThreadWorkaround(stopper, reset, shutdownPi, startTime, logger)
    
    logger.debug("Starting userInterfaceThread thread")
    userInterfaceThread.start()
    logger.debug("Starting playerInterfaceThread thread")
    playerInterfaceThread.start()

    logger.debug("Starting shutdownTimerThread thread")
    shutdownTimerThread.start()
    
    # File acting as a switch for this application:
    switchFile = "CHARLIEBERT_STOP"
    if os.path.exists(switchFile):
        logger.debug("Removing switch file CHARLIEBERT_STOP")
        os.remove(switchFile)
    
            
    try:
        while not os.path.exists(switchFile) and not stopper.is_set():
            pass
        
        if os.path.exists(switchFile):
            logger.debug("Stop requested using the flag file '{}'".format(switchFile))
            os.remove(switchFile)

           
    except KeyboardInterrupt:
        logger.debug("Stop requested")
        stopper.set() 
        reset.set() 
    
    finally:
        if not stopper.is_set():
            stopper.set() 
        if not reset.is_set():
            reset.set() 
            
            
        while not q.empty():
            q.get()
        q.put(None)
        
        # Write configuration to disk when exiting the program
        writeConfig(config)
        
    if shutdownPi.is_set():
        logger.debug("Shutting down Pi now")
        # Hack to work around the need for a password when using sudo:
        # sudo chmod u+s /sbin/shutdown
        # (using sleep to delay the actual shutdown, so as to leave time for the python program to quit properly)
        #logger.debug("/sbin/shutdown -h now")
        os.system("/sbin/shutdown -h now")
            

if __name__ == '__main__':
    # Logging
#    logging.basicConfig(filename='charliebert.log', 
#                         level=logging.DEBUG, 
#                         format='%(asctime)s %(name)s %(levelname)s:%(message)s', 
#                         datefmt='%Y-%m-%d %H:%M:%S')
    logFormatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(filename)s:%(lineno)d) %(message)s')
    logFile = 'charliebert.log'
    logHandler = RotatingFileHandler(logFile, mode='a', maxBytes=5*1024*1024, 
                                     backupCount=2, encoding=None, delay=0)
    logHandler.setFormatter(logFormatter)
    logHandler.setLevel(logging.DEBUG)
    logger = logging.getLogger('root')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logHandler)    

    logging.getLogger("soco").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # PID (for status)
    pid = os.getpid()
    with open("PID_CHARLIEBERT", "a") as pidFile:
        pidFile.write("{:d}\n".format(pid))

    config = configparser.ConfigParser()
    initConfig(logger, config)
    
    logger.info("Starting charliebert")             
    charliebert(logger, config)
    logger.info("Quitting charliebert")
