from mpd import MPDClient
import logging
from logging.handlers import RotatingFileHandler
from time import sleep
import time
from cookielib import logger

class McpInterface():
    def __init__(self, logger):
        # Logging mechanism
        self.logger = logger
        
        # Initialize MCP client
        self.client = MPDClient()
        
        # Currently selected Sonos speaker
        #self.speaker = None
        
        self.connected = False
        
        # Index of the first track of the current playlist in the queue 
        self.indexBegPlaylist = 0
        # Number of items in the current playlist
        self.playlistSize = 0
        # Name of the last selected playlist
        self.playlistName = ""
        # Size of the queue
        self.queueSize = 0
        
        # Limitations
        self.minVolume = 10 # Make sure the music is audible...
        self.maxVolume = 50 # ...but not painful
        self.minTimePlaylist = 10 # (seconds) Time before starting another playlist is allowed
        self.timeLastStartPlaylist = time.time() - self.minTimePlaylist # Make sure we can start a playlist right away
        self.cancelOffsetStartPlaylist = False # True if the playlist has been stopped before the end of the offset time
        
    def connect(self): 
        try:
            client.connect("localhost", 6600)
        except ConnectionError as ce:
            if ce.args == "Already connected":
                pass
            else:
                self.connected = False
                return
            
        self.connected = True
        
    def printSpeakerList(self):
        try:
            self.connect()
        except:
            self.logger.error("Problem establishing connection to the MCP system")
            return

    def prepareRoom(self, room):
        try:
            self.connect()
        except:
            self.logger.error("Problem establishing connection to the MCP system")
            return False
                
        return True
                        
    def getSpeaker(self, room):
        return None

    def offsetStartPlaylist(self, playlistName):
        currentTime = time.time()
        if currentTime - self.timeLastStartPlaylist < self.minTimePlaylist:
            self.logger.debug("Discarding command to start playlist {} (issued {} after the last playlist command)".format(playlistName, currentTime - self.timeLastStartPlaylist))
            return True
        
        self.timeLastStartPlaylist = currentTime
        self.cancelOffsetStartPlaylist = False
        return False
        
    def startPlaylist(self, playlistName, room):
        # Discard commands that are issued too briefly after the last
        if not self.cancelOffsetStartPlaylist and self.offsetStartPlaylist(playlistName):
            return
        
        try:
            sp = self.getSpeaker(room)
            
            if playlistName == self.playlistName:
                # Starting the same playlist again: Just start playing from the beginning again
                # without appending the tracks to the queue once more
                sp.play_from_queue(self.indexBegPlaylist)
                return
            
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            
            playlist = sp.get_sonos_playlist_by_attr('title', playlistName)
            self.playlistName = playlistName
            oldQueueSize = sp.queue_size
            self.indexBegPlaylist = oldQueueSize
            sp.add_to_queue(playlist)
            self.queueSize = sp.queue_size
            self.playlistSize = self.queueSize - oldQueueSize
            sp.play_from_queue(self.indexBegPlaylist)
        except:
            self.logger.error("Problem playing playlist '{}'".format(playlistName))
            return

    def playTrackNb(self, trackNb, room):
        if trackNb < 1:
            self.logger.error("Cannot play track number {:d}".format(trackNb))
            return 
        
        trackIndex = self.indexBegPlaylist + trackNb - 1
        
        if trackIndex >= self.queueSize:
            self.logger.error("Track number {:d} too large (index: {:d}, playlist size: {:d})".format(trackNb, trackIndex, self.playlistSize))
            return
        
        try:
            sp = self.getSpeaker(room)
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            sp.play_from_queue(trackIndex)
        except:
            self.logger.error("Problem playing track number '{:d}' (track index: {:d}, queue size: {:d})".format(trackNb, trackIndex, self.queueSize))
            return    

    def togglePlayPause(self, room):
        try:
            currentState = None
            sp = self.getSpeaker(room)
            currentState = sp.get_current_transport_info()[u'current_transport_state']
            
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            
            if currentState == 'PLAYING':
                sp.pause()
                self.cancelOffsetStartPlaylist = True
            else:
                sp.play()
        except:
            self.logger.error("Problem toggling play/pause (current state: {})".format(currentState))

    def skipToNext(self, room):
        try:
            sp = self.getSpeaker(room)
            
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            
            sp.next()
            self.cancelOffsetStartPlaylist = True
        except:
            self.logger.error("Problem skipping to next song")
          
    def skipToPrevious(self, room):
        try:
            sp = self.getSpeaker(room)
            
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            
            sp.previous()
            self.cancelOffsetStartPlaylist = True
        except:
            self.logger.error("Problem skipping to previous song")
          
    def adjustVolume(self, volumeDelta, room):
        try:
            oldVol = None
            newVol = None
            volumeDelta = int(round(volumeDelta))
            sp = self.getSpeaker(room)
            oldVol = sp.volume
            newVol = oldVol + volumeDelta
            
            # Enforce volume limits
            if newVol < self.minVolume:
                self.logger.debug("Upping volume to {:d} [would have been {:d}]".format(self.minVolume, newVol))
                sp.volume = self.minVolume
            elif newVol > self.maxVolume:
                self.logger.debug("Limiting volume to {:d} [would have been {:d}]".format(self.maxVolume, newVol))
                sp.volume = self.maxVolume
            else:
                sp.volume += volumeDelta
            newVol = sp.volume
        except:
            self.logger.error("Problem adjusting volume (old volume: {:d}, new volume: {:d}, delta: {:d})".format(oldVol, newVol, volumeDelta))

    def soundCheck(self, room):
        vol = -1
        newVol = -1
        try:
            sp = self.getSpeaker(room)
            vol = sp.volume
            
            # Enforce volume limits
            if vol < self.minVolume:
                self.logger.debug("Upping volume to {:d} [would have been {:d}]".format(self.minVolume, newVol))
                sp.volume = self.minVolume
            elif vol > self.maxVolume:
                self.logger.debug("Limiting volume to {:d} [would have been {:d}]".format(self.maxVolume, newVol))
                sp.volume = self.maxVolume
            newVol = sp.volume
        except:
            self.logger.error("Problem adjusting volume (old volume: {:d}, new volume: {:d})".format(vol, newVol))

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
        mi.printSpeakerList()
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
        
