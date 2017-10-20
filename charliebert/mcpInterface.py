from playerInterface import PlayerInterface
from mpd import MPDClient
import logging
from logging.handlers import RotatingFileHandler
from time import sleep
import time
from cookielib import logger

class McpInterface(PlayerInterface):
    def __init__(self, logger):
        # Logging mechanism
        self.logger = logger
        
        # Initialize PlayerInterface
        super(SonosInterface, self).__init__(self.logger)
        
        # Initialize MCP client
        self.client = MPDClient()
        self.client.timeout = 10
        
        
    def connect(self): 
        try:
            try:
                if self.connected:
                    self.disconnect()
            except:
                pass
                
            self.client.connect("localhost", 6600)
            self.connected = True
        except:
            self.connected = False
            
    def disconnect(self):
        try:
            self.client.close()
            self.client.disconnect()
        except:
             pass
         
        self.connected = False

    def prepareRoom(self, room):
        try:
            self.connect()
        except:
            self.logger.error("Problem establishing connection to the MCP system")
            return False
                
        self.disconnect()
        
        return True
        
    def startPlaylist(self, playlistName, room):
        # Discard commands that are issued too briefly after the last
        if not self.cancelOffsetStartPlaylist and self.offsetStartPlaylist(playlistName):
            return
        
        self.connect()
        
        try:    
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            
            if playlistName == self.playlistName:
                # Starting the same playlist again: Just start playing from the beginning again
                # without appending the tracks to the queue once more
                client.play(0)
                return        
            
            self.client.clear()
            self.client.load(playlistName)
            self.client.play(0)
            
            self.playlistSize = len(self.client.playlistinfo())
            self.queueSize = self.playlistSize
            
        except:
            self.logger.error("Problem playing playlist '{}'".format(playlistName))
            return
        
        self.disconnect()

    def playTrackNb(self, trackNb, room):
        if trackNb < 1:
            self.logger.error("Cannot play track number {:d}".format(trackNb))
            return 
        
        trackIndex = trackNb - 1
        
        if trackIndex >= self.queueSize:
            self.logger.error("Track number {:d} too large (index: {:d}, playlist size: {:d})".format(trackNb, trackIndex, self.playlistSize))
            return
                
        self.connect()
                
        try:
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            
            self.client.play(trackIndex)

        except:
            self.logger.error("Problem playing track number '{:d}' (track index: {:d}, queue size: {:d})".format(trackNb, trackIndex, self.queueSize))
            return    
        
        self.disconnect()
        
    def togglePlayPause(self, room):        
        self.connect()
        
        try:
            currentState = None
            currentState = self.client.status()['state']
            
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            
            if currentState == 'play':
                self.client.pause()
                self.cancelOffsetStartPlaylist = True
            else:
                self.client.play()
        except:
            self.logger.error("Problem toggling play/pause (current state: {})".format(currentState))
        
        self.disconnect()
        
    def skipToNext(self, room):
        self.connect()
        
        try:
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            
            self.client.next()
            self.cancelOffsetStartPlaylist = True
        except:
            self.logger.error("Problem skipping to next song")
        
        self.disconnect()
                  
    def skipToPrevious(self, room):
        self.connect()

        try:
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            
            self.client.previous()
            self.cancelOffsetStartPlaylist = True
        except:
            self.logger.error("Problem skipping to previous song")

        self.disconnect()
          
    def adjustVolume(self, volumeDelta, room):
        self.connect()
        
        try:
            oldVol = None
            newVol = None
            volumeDelta = int(round(volumeDelta))
            
            oldVol = int(self.client.status()['volume'])
            newVol = oldVol + volumeDelta
            
            # Enforce volume limits
            if newVol < self.minVolume:
                self.logger.debug("Upping volume to {:d} [would have been {:d}]".format(self.minVolume, newVol))
                self.client.setvol(self.minVolume)
            elif newVol > self.maxVolume:
                self.logger.debug("Limiting volume to {:d} [would have been {:d}]".format(self.maxVolume, newVol))
                self.client.setvol(self.maxVolume)
            else:
                self.client.setvol(newVol)
            newVol = int(self.client.status()['volume'])
        except:
            self.logger.error("Problem adjusting volume (old volume: {:d}, new volume: {:d}, delta: {:d})".format(oldVol, newVol, volumeDelta))

        self.disconnect()
        
    def soundCheck(self, room):
        self.connect()
        
        vol = -1
        newVol = -1
        try:
            vol = int(self.client.status()['volume'])
            
            # Enforce volume limits
            if vol < self.minVolume:
                self.logger.debug("Upping volume to {:d} [would have been {:d}]".format(self.minVolume, newVol))
                self.client.setvol(self.minVolume)
            elif vol > self.maxVolume:
                self.logger.debug("Limiting volume to {:d} [would have been {:d}]".format(self.maxVolume, newVol))
                self.client.setvol(self.maxVolume)
            newVol = int(self.client.status()['volume'])
        except:
            self.logger.error("Problem adjusting volume (old volume: {:d}, new volume: {:d})".format(vol, newVol))

        self.disconnect()
        
if __name__ == '__main__':
    # Logging
#    logging.basicConfig(filename='sonosInterface.log', 
#                        level=logging.DEBUG, 
#                        format='%(asctime)s %(name)s %(levelname)s:%(message)s', 
#                        datefmt='%Y-%m-%d %H:%M:%S')
    logFormatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(pathname)s:%(lineno)d) %(message)s')
    logFile = 'sonosInterface.log'
    logHandler = RotatingFileHandler(logFile, mode='a', maxBytes=5*1024*1024, 
                                     backupCount=2, encoding=None, delay=0)
    logHandler.setFormatter(logFormatter)
    logHandler.setLevel(logging.DEBUG)
    logger = logging.getLogger('root')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logHandler)    
        
    logger.info("Creating instance of McpInterface") 
    mi = McpInterface(logger)
    try:
        mi.startPlaylist("zCharliebert_A01", "Office")
        sleep(5)
        mi.playTrackNb(3, "Office")
        sleep(5)
        mi.startPlaylist("zCharliebert_A02", "Office")
        sleep(5)
        mi.playTrackNb(3, "Office")
        sleep(5)
        mi.togglePlayPause("Office")
        sleep(5)
        mi.togglePlayPause("Office")
        sleep(5)
        mi.skipToNext("Office")
        sleep(5)
        mi.skipToNext("Office")
        sleep(5)
        mi.skipToPrevious("Office")
        sleep(5)
        mi.skipToPrevious("Office")
        sleep(5)
        mi.adjustVolume(10, "Office")
        sleep(5)
        mi.adjustVolume(10, "Office")
        sleep(5)
        mi.adjustVolume(-10, "Office")
        sleep(5)
        mi.adjustVolume(-10, "Office")
    except KeyboardInterrupt:
        logger.info("Stop (Ctrl-C from __main__)") 
        print("Stop (Ctrl-C) [from main]")
        
