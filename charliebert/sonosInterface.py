from playerInterface import PlayerInterface
import soco
import logging
from logging.handlers import RotatingFileHandler
from time import sleep
import time

class SonosInterface(PlayerInterface):
    def __init__(self, logger):
        # Logging mechanism
        self.logger = logger
        # Initialize Sonos system characteristics
        self.list_sonos = []
    
        self.speakers = {}
        self.names = []
        
        # Currently selected Sonos speaker
        self.speaker = None
        
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
        # Prepare info about Sonos speakers
        self.speakers = {}
        self.names = []
        
        list_sonos = list(soco.discover())
    
        if len(list_sonos) == 0:
            self.connected = False
            return
    
        for speaker in list_sonos:
            name = speaker.get_speaker_info()['zone_name']
            self.names.append(name)
            self.speakers[name] = speaker
            
        self.connected = True
        
    def printSpeakerList(self):
        try:
            self.connect()
        except:
            self.logger.error("Problem establishing connection to the Sonos system")
            return

        for name, speaker in self.speakers.items():
            print("Speaker: {}".format(name))
    
    def prepareRoom(self, room):
        try:
            self.connect()
        except:
            self.logger.error("Problem establishing connection to the Sonos system")
            return False
        
        if room not in self.names:
            self.logger.error("Room '{}' not available in the Sonos system".format(room))
            return False
        
        return True
                        
    def getSpeaker(self, room):
        try:
            # Try to access the stored object
            if self.speaker.get_speaker_info()['zone_name'] == room:
                # All good, the currently active speaker's name corresponds to our parameter
                return self.speaker 
        except:
            if self.prepareRoom(room) is False:
                self.logger.error("Cannot prepare room {}".format(room))
                return None
            
            # There was a problem: Redefine the speaker
            sp = self.speakers[room]
            
            return sp.group.coordinator
        
    def startPlaylist(self, playlistName, room):
        # Discard commands that are issued too briefly after the last
        if not self.cancelOffsetStartPlaylist and self.offsetStartPlaylist(playlistName):
            return
        
        try:
            sp = self.getSpeaker(room)
            
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            
            if playlistName == self.playlistName:
                # Starting the same playlist again: Just start playing from the beginning again
                # without appending the tracks to the queue once more
                sp.play_from_queue(self.indexBegPlaylist)
                return
            
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

    def isCurrentlyPlaying(self, room):
        try:
            currentState = None
            sp = self.getSpeaker(room)
            currentState = sp.get_current_transport_info()[u'current_transport_state']
            
            return currentState == 'PLAYING'
        
        except:
            self.logger.error("Problem toggling play/pause (current state: {})".format(currentState))
            return False
            
            
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
        
    logger.info("Creating instance of SonosInterface") 
    si = SonosInterface(logger)
    try:
        si.printSpeakerList()
        si.startPlaylist("zCharliebert_A01", "Office")
        sleep(5)
        si.playTrackNb(3, "Office")
        sleep(5)
        si.startPlaylist("zCharliebert_A02", "Office")
        sleep(5)
        si.playTrackNb(3, "Office")
        sleep(5)
        si.togglePlayPause("Office")
        sleep(5)
        si.togglePlayPause("Office")
        sleep(5)
        si.skipToNext("Office")
        sleep(5)
        si.skipToNext("Office")
        sleep(5)
        si.skipToPrevious("Office")
        sleep(5)
        si.skipToPrevious("Office")
        sleep(5)
        si.adjustVolume(10, "Office")
        sleep(5)
        si.adjustVolume(10, "Office")
        sleep(5)
        si.adjustVolume(-10, "Office")
        sleep(5)
        si.adjustVolume(-10, "Office")
    except KeyboardInterrupt:
        logger.info("Stop (Ctrl-C from __main__)") 
        print("Stop (Ctrl-C) [from main]")
        
