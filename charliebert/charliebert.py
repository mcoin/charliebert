import time
import threading
from time import sleep
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
try:
    import ConfigParser as configparser # For python 2
except:
    import configparser # For python 3


configFileName = 'charliebert.config'

class UserInterfaceThread(threading.Thread):
    def __init__(self, stopper, u2pQ, p2uQ, reset, logger, config):
        super(UserInterfaceThread, self).__init__()
        self.config = config
        self.stopper = stopper
        self.u2pQ = u2pQ
        self.p2uQ = p2uQ
        self.reset = reset
        self.logger = logger

        self.ui = UserInterface(self.logger)
        
    def run(self):
        self.logger.debug("UserInterfaceThread starting")
        self.ui.run(self.stopper, self.u2pQ, self.p2uQ, self.reset)
        self.logger.debug("UserInterfaceThread stopping")

class PlayerInterfaceThread(threading.Thread):
    def __init__(self, stopper, u2pQ, p2uQ, shutdownPi, logger, config):
        super(PlayerInterfaceThread, self).__init__()
        self.config = config        
        self.logger = logger
        self.stopper = stopper
        self.u2pQ = u2pQ
        self.p2uQ = p2uQ
        
        self.availableRooms = ('Bedroom', 
                               'Bathroom', 
                               'Office', 
                               'Kitchen', 
                               'Living Room', 
                               'Charlie\'s Room', 
                               'Wohnzimmer', 
                               'Obenauf',
                               'Charliebert')
        self.availableRoomIndices = {'Bedroom': 1, 
                               'Bathroom': 2, 
                               'Office': 3, 
                               'Kitchen': 4, 
                               'Living Room': 5, 
                               'Charlie\'s Room': 6, 
                               'Wohnzimmer': 1, 
                               'Obenauf': 2,
                               'Charliebert': 0}
                
        self.room = "Office"
        #self.room = "Bedroom"
        self.availableNetworks = ('aantgr', 'AP2')
        self.availableNetworkIndices = {'aantgr': 2, 'AP2': 1, 'charliebert': 3}
        self.network = "aantgr"
        self.availablePlaylistBasenames = "zCharliebert"
        self.playlistBasename = "zCharliebert"
        self.availablePlayers = ('Sonos', 'Mpd')
        self.player = "Sonos"
        
        self.readConfig()
        
        self.sendInitialNetworkAndRoomState()
        
        self.parser = re.compile("^([A-Z/]+)(\s+([A-Z]+))*(\s+([-0-9]+))*\s*$")
        self.shutdownPi = shutdownPi

        self.si = SonosInterface(self.logger)
        self.mi = MpdInterface(self.logger)

        if self.player == 'Sonos':        
            self.pi = self.si
        else:
            self.pi = self.mi

    def readConfig(self):
        try:
            cfgRoom = config.get('PlayerInterface', 'room')
            if cfgRoom in self.availableRooms:
                self.room = cfgRoom
            else:
                self.logger.error("Unrecognized room from config: {}".format(cfgRoom))
        except:
            self.logger.error("Problem encountered when attempting to set room from config")
            
        try:
            cfgNetwork = config.get('PlayerInterface', 'network')
            if cfgNetwork is None:
                self.logger.debug("No network defined in config")
            else:
                if cfgNetwork in self.availableNetworks:
                    self.network = cfgNetwork
                else:
                    self.logger.error("Unrecognized network from config: {}".format(cfgNetwork))
        except:
            self.logger.error("Problem encountered when attempting to set network from config")

        try:
            cfgPlaylistBasename = config.get('PlayerInterface', 'playlistBasename')
            if cfgPlaylistBasename in self.availablePlaylistBasenames:
                self.playlistBasename = cfgPlaylistBasename
            else:
                self.logger.error("Unrecognized playlist basename from config: {}".format(cfgPlaylistBasename))
        except:
            self.logger.error("Problem encountered when attempting to set playlist basename from config")

        try:
            cfgPlayer = config.get('PlayerInterface', 'player')
            if cfgPlayer in self.availablePlayers:
                self.player = cfgPlayer
            else:
                self.logger.error("Unrecognized player from config: {}".format(cfgPlayer))
        except:
            self.logger.error("Problem encountered when attempting to set player from config")
                    
    def saveConfig(self):
        self.logger.debug("Saving current configuration of the player interface")
        self.logger.debug("Current room: {}".format(self.room))
        self.logger.debug("Current network: {}".format(self.network))
        try:
            config.set('PlayerInterface', 'room', self.room)
            config.set('PlayerInterface', 'network', self.network)
            config.set('PlayerInterface', 'playlistBasename', self.playlistBasename)
            config.set('PlayerInterface', 'player', self.player)
        except:
            self.logger.debug("Error encountered while saving current configuration of the player interface")

    def sendInitialNetworkAndRoomState(self):
        try:
            self.logger.debug("network: {}".format(self.network))
            self.logger.debug("room: {}".format(self.room))
            self.logger.debug("player: {}".format(self.player))
            networkIndex = -1
            roomIndex = -1
            if self.player == "Mpd":
                networkIndex = self.availableNetworkIndices["charliebert"]
                self.logger.debug("network index: {}".format(networkIndex))
                roomIndex = 0
            else:
                networkIndex = self.availableNetworkIndices[self.network]
                self.logger.debug("network index: {}".format(networkIndex))
                roomIndex = self.availableRoomIndices[self.room]
                self.logger.debug("room index: {}".format(roomIndex))
            self.logger.debug("Sending initial network ({:d}) and room ({:d}) indices to the user interface".format(networkIndex, roomIndex))
            self.p2uQ.put("NETWORK/ROOM {:d}; {:d}".format(networkIndex, roomIndex))
        except:
            self.logger.error("An error occurred while sending the initial network and room indices to the user interface")

    def run(self):
        self.logger.debug("PlayerInterfaceThread starting")
        try:
            while not self.stopper.is_set():
                #time.sleep(1)
                self.logger.debug("Player Interface: Waiting for a command to execute")
                command = self.u2pQ.get()
                if command is None:
                    break
                self.logger.debug("Player Interface: Obtained command {}".format(command))
                self.u2pQ.task_done()

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
                    elif m.group(1) == "ALTPLAYLIST":
                        bank = m.group(3)
                        bankNb = int(m.group(5))
                        self.logger.debug("Command PLAYLIST: {} {:d}".format(bank, bankNb))
                        playlistName = "{0}_{1}{2:02d}".format(self.playlistBasename, bank, bankNb)
                        self.logger.debug("Starting playlist {}".format(playlistName))
                        self.pi.startPlaylistAlt(playlistName, self.room)
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

                    elif m.group(1) == "COMMAND":
                        commandNb = int(m.group(5))
                        self.logger.debug("Command COMMAND: {:d}".format(commandNb))

                        if commandNb == 1:
                            self.p2uQ.put("PROGRESS START")
                            time.sleep(10)

			    #time = 0
			    #timeInterval = 1
    			    #timer = threading.Event()
			    #duration = 10
            		    #while time < duration:
			#	timer.wait(timeInterval)
			#	time += timeInterval

                            self.p2uQ.put("PROGRESS STOP")
                        elif commandNb == 10:
                            # Import sonos playlists - soft 
                            # (only retrieve not yet exported sonos playlists,
                            # and only copy not yet copied music files)
                            self.logger.debug("Exporting sonos playlists...")
                            self.si.exportAllPlaylists(u'Office')            
                            self.logger.debug("Done.")
                            
                            self.logger.debug("Importing playlists into MPD...")
                            self.mi.importAllPlaylists(u'Office')            
                            self.logger.debug("Done.")                                                                                                   
                        elif commandNb == 11:
                            # Import sonos playlists - medium
                            # (renew sonos playlist definitions,
                            # but only copy not yet copied music files)
                            self.logger.debug("Exporting sonos playlists...")
                            self.si.exportAllPlaylists(u'Office', True)            
                            self.logger.debug("Done.")
                            
                            self.logger.debug("Importing playlists into MPD...")
                            self.mi.importAllPlaylists(u'Office')            
                            self.logger.debug("Done.")                                                                                                   
                        elif commandNb == 12:
                            # Import sonos playlists - hard
                            # (renew sonos playlist definitions,
                            # and also overwrite already copied music files)
                            self.logger.debug("Exporting sonos playlists...")
                            self.si.exportAllPlaylists(u'Office', True)            
                            self.logger.debug("Done.")
                            
                            self.logger.debug("Importing playlists into MPD...")
                            self.mi.importAllPlaylists(u'Office', True)
                            self.logger.debug("Done.")                                                                                                   

                        else:
                            self.logger.error("Command COMMAND: {:d}: Command does not exist".format(commandNb))

                        self.logger.debug("Current room: {}".format(self.room))
                        self.logger.debug("Current network: {}".format(self.network))
                        
                        # Save current configuration for next start
                        self.saveConfig()

                    elif m.group(1) == "ROOM":
                        roomNb = int(m.group(5))
                        self.logger.debug("Command ROOM: {:d}".format(roomNb))

                        if self.network == "aantgr":
                            if roomNb == 1:
                                self.room = "Bedroom"
                            elif roomNb == 2:
                                self.room = "Bathroom"
                            elif roomNb == 3:
                                self.room = "Office"  
                            elif roomNb == 4:
                                self.room = "Kitchen"  
                            elif roomNb == 5:
                                self.room = "Living Room"  
                            elif roomNb == 6:
                                self.room = "Charlie's Room"
                            elif roomNb == 9:
                                self.logger.debug("Exporting sonos playlists...")
                                self.si.exportAllPlaylists(u'Office')            
                                self.logger.debug("Done.")
                                
                                self.logger.debug("Importing playlists into MPD...")
                                self.mi.importAllPlaylists(u'Office')            
                                self.logger.debug("Done.")                                                                                                   
                            else:
                                self.logger.error("Command ROOM: {:d}: Room does not exist".format(roomNb))
                        elif self.network == "AP2":
                            if roomNb % 2 == 0:
                                self.room = "Wohnzimmer"
                            else:
                                self.room = "Obenauf"
                        else:
                            self.room = "Charliebert"

                        self.logger.debug("Current room: {}".format(self.room))
                        
                        # Save current configuration for next start
                        self.saveConfig()

                    elif m.group(1) == "NET":
                        networkNb = int(m.group(5))
                        self.logger.debug("Command NET: {:d}".format(networkNb))

                        if networkNb == 1 or networkNb == 2:
                            if self.player != "Sonos":
                                self.player = "Sonos"
                                self.logger.debug("Switching player to Sonos")
                                self.pi = self.si
                            if networkNb == 2:
                                self.changeNetwork("aantgr")
                            elif networkNb == 1:
                                self.changeNetwork("AP2")
                        elif networkNb == 3:
                            if self.player != "Mpd":
                                self.player = "Mpd"
                                self.logger.debug("Switching player to MPD")
                                self.pi = self.mi
                        else:
                            self.logger.error("Command NET {:d}: Network does not exist".format(networkNb))

                        self.logger.debug("Current Network: {}".format(self.network))
                        
                        # Save current configuration for next start
                        self.saveConfig()
                    else:
                       raise 
                except:
                    self.logger.error("Unrecognized command: '{}'".format(command))
                
        except KeyboardInterrupt:
            self.logger.debug("Player Interface stopped (Ctrl-C)")
        self.logger.debug("PlayerInterfaceThread stopping")

        # Save config before quitting (possibly useless, as it may occur only after writeConfig())
        self.saveConfig()
        
    # Returns True in case the currently selected player is currently playing
    def isCurrentlyPlaying(self):
        return self.pi.isCurrentlyPlaying(self.room)

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
    def __init__(self, stopper, reset, shutdownFlag, startTime, playerInterfaceThread, logger):
        super(ShutdownTimerThread, self).__init__()
        self.stopper = stopper
        self.reset = reset
        self.shutdownFlag = shutdownFlag
        self.startTime = startTime
        self.playerInterfaceThread = playerInterfaceThread
        self.logger = logger
        #self.shutdownTimePeriod = 1800 # s
        self.shutdownTimePeriod = 600 # s
        #self.shutdownTimePeriod = 10 # s
        self.maxNbCanceledShutdowns = 3 # After N canceled attempts at shutting down (music still playing), do shut down anyhow
        self.nbCanceledShutdowns = 0 
        
    def run(self):
        self.logger.debug("ShutdownTimerThread starting")
        while not self.stopper.is_set():
            while not self.reset.wait(self.shutdownTimePeriod):
                if self.isCurrentlyPlaying() and self.nbCanceledShutdowns < self.maxNbCanceledShutdowns - 1:
                    self.logger.debug("ShutdownTimerThread: Canceling reset since music is currently playing")
                    self.reset.clear()
                    self.nbCanceledShutdowns += 1
                elif not self.stopper.is_set():
                    self.logger.debug("ShutdownTimerThread: Setting flag to shut down the Pi")
                    self.logger.debug("Original start time: {}".format(self.startTime))
                    self.shutdownFlag.set()
                    self.stopper.set()
                
            if self.reset.is_set() and not self.stopper.is_set():
                self.logger.debug("ShutdownTimerThread: Resetting the shutdown timer")
                self.reset.clear()
                self.nbCanceledShutdowns = 0
            
        self.logger.debug("ShutdownTimerThread stopping")
        
    # Returns True in case the currently selected player is currently playing
    def isCurrentlyPlaying(self):
        self.logger.debug("ShutdownTimerThread Finding out whether music is still playing")
        return self.playerInterfaceThread.isCurrentlyPlaying()
        
# Variant that does not rely on the "hardware" clock
class ShutdownTimerThreadWorkaround(ShutdownTimerThread):
    def __init__(self, stopper, reset, shutdownFlag, startTime, playerInterfaceThread, logger):
        super(ShutdownTimerThreadWorkaround, self).__init__(stopper, reset, shutdownFlag, startTime, playerInterfaceThread, logger)
        self.time = 0
        self.timeInterval = 5
        
    def run(self):
        self.logger.debug("ShutdownTimerThreadWorkaround starting")
        while not self.stopper.is_set():
            self.reset.clear()
            self.time = 0
            self.logger.debug("ShutdownTimerThreadWorkaround: Starting loop until shutdownTimePeriod or stopper or reset")
            while self.time < self.shutdownTimePeriod:
                self.stopper.wait(self.timeInterval)
                self.time += self.timeInterval
                
                # Exit right away if stop is requested
                if self.stopper.is_set():
                    self.logger.debug("ShutdownTimerThreadWorkaround: Stop requested, exiting right away (1)")
                    break
                
                if self.reset.is_set():
                    self.logger.debug("ShutdownTimerThreadWorkaround: Resetting the shutdown timer")
                    break
            
            self.logger.debug("ShutdownTimerThreadWorkaround: Out of loop until shutdownTimePeriod or stopper or reset")

            # Exit right away if stop is requested
            if self.stopper.is_set():
                self.logger.debug("ShutdownTimerThreadWorkaround: Stop requested, exiting right away (2)")
                break
                    
            if self.reset.is_set():
                # Just restart the loop
                self.logger.debug("ShutdownTimerThreadWorkaround: Resetting the shutdown timer (restarting the loop)")
                self.nbCanceledShutdowns = 0
            elif self.isCurrentlyPlaying() and self.nbCanceledShutdowns < self.maxNbCanceledShutdowns - 1:
                # Do not shut down the Pi as we are still playing music
                self.logger.debug("ShutdownTimerThreadWorkaround: Canceling shutdown since music is currently playing")
                self.nbCanceledShutdowns += 1
                self.logger.debug("ShutdownTimerThreadWorkaround: Nb of canceled shutdowns = {:d}".format(self.nbCanceledShutdowns))
            else:
                # Music is no longer playing and we had no sign of activity for a while: Shut down the Pi
                self.logger.debug("ShutdownTimerThreadWorkaround: Setting flag to shut down the Pi")
                self.shutdownFlag.set()
                self.stopper.set()
                

def initConfig(logger, config):
    logger.debug("Setting initial config")
    config.add_section('PlayerInterface')
    config.set('PlayerInterface', 'room', 'Office')
    config.set('PlayerInterface', 'network', 'aantgr')
    config.set('PlayerInterface', 'playlistBasename', 'zCharliebert')
    config.set('PlayerInterface', 'player', 'sonos')

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
    # Queues for commands
    u2pQ = Q.Queue()
    p2uQ = Q.Queue()
    #
    shutdownPi = threading.Event()
    reset = threading.Event()
    startTime = "charliebert start: {}".format(datetime.now())
    logger.debug("{}".format(startTime))
    
    userInterfaceThread = UserInterfaceThread(stopper, u2pQ, p2uQ, reset, logger, config)
    playerInterfaceThread = PlayerInterfaceThread(stopper, u2pQ, p2uQ, shutdownPi, logger, config)

    #shutdownTimerThread = ShutdownTimerThread(stopper, reset, shutdownPi, startTime, playerInterfaceThread, logger)
    shutdownTimerThread = ShutdownTimerThreadWorkaround(stopper, reset, shutdownPi, startTime, playerInterfaceThread, logger)
    
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
            
            
        while not u2pQ.empty():
            u2pQ.get()
        u2pQ.put(None)
        

        # Write configuration to disk when exiting the program
        writeConfig(logger, config)
        
    if shutdownPi.is_set():
        logger.debug("Shutting down Pi now")
        # Hack to work around the need for a password when using sudo:
        # sudo chmod u+s /sbin/shutdown
        # (using sleep to delay the actual shutdown, so as to leave time for the python program to quit properly)
        #logger.debug("/sbin/shutdown -h now")
        os.system("sleep 1; /sbin/shutdown -h now")
            

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
