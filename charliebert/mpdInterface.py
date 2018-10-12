from playerInterface import PlayerInterface
from mpd import MPDClient
import logging
from logging.handlers import RotatingFileHandler
from time import sleep
import time
from cookielib import logger
from playerInterface import Playlist

class MpdInterface(PlayerInterface):
    def __init__(self, logger):
        # Logging mechanism
        self.logger = logger
        
        # Initialize PlayerInterface
        #super(MpdInterface, self).__init__(self.logger)
        PlayerInterface.__init__(self, self.logger)
        
        # Initialize MCP client
        self.client = MPDClient()
        self.client.timeout = 10
        
        # Limitations
        self.minVolume = 20 # Make sure the music is audible...
        self.maxVolume = 80 # ...but not painful
		
        
    def connect(self): 
        self.logger.debug("Connecting")
        try:
            try:
                if self.connected:
                    self.logger.debug("Already connected: Attempt disconnecting")
                    self.disconnect()
            except:
                pass
                
            self.logger.debug("Attempt connecting")
            self.client.connect("localhost", 6600)
            self.logger.debug("Connected")
            self.connected = True
        except:
            self.logger.debug("Not connected")
            self.connected = False
            
    def disconnect(self):
        self.logger.debug("Disconnecting")
        try:
            self.logger.debug("Closing")
            self.client.close()
            self.logger.debug("Disconnecting")
            self.client.disconnect()
        except:
             pass
         
        self.logger.debug("Not connected")
        self.connected = False

    def prepareRoom(self, room):
        try:
            self.connect()
        except:
            self.logger.error("Problem establishing connection to the MCP system")
            return False
                
        self.disconnect()
        
        return True

    def startPlaylistBare(self, playlistName, room):
        # Make sure we won't go deaf right now
        self.soundCheck(room)
        
        if playlistName == self.playlistName:
            # Starting the same playlist again: Just start playing from the beginning again
            # without appending the tracks to the queue once more
            self.logger.debug("Playlist {} already active: Restarting from first song".format(playlistName))
            client.play(0)
            return        
        
        self.logger.debug("Clearing playlist")
        self.client.clear()
        self.logger.debug("Loading playlist")
        self.client.load(playlistName)
        self.logger.debug("Starting playlist")
        self.client.play(0)
        
        self.playlistSize = len(self.client.playlistinfo())
        self.queueSize = self.playlistSize
        self.logger.debug("Number of songs in the playlist: {:d}".format(self.playlistSize))        
    
    def startPlaylist(self, playlistName, room):
        self.logger.debug("Starting playlist {}".format(playlistName))
        # Discard commands that are issued too briefly after the last
        if not self.cancelOffsetStartPlaylist and self.offsetStartPlaylist(playlistName):
            self.logger.debug("Aborting: Playlist already started not long ago")
            return
        
        self.connect()
        
        try:    
            self.startPlaylistBare(playlistName, room)
        except:
            self.logger.error("Problem playing playlist '{}'".format(playlistName))
            return
        
        self.disconnect()        
        
    def startPlaylistAlt(self, playlistName, room):
        self.logger.debug("Starting playlist {}".format(playlistName))
        # Discard commands that are issued too briefly after the last
        if not self.cancelOffsetStartPlaylist and self.offsetStartPlaylist(playlistName):
            self.logger.debug("Aborting: Playlist already started not long ago")
            return
        
        self.connect()
        
        try:    
            altPlaylistName = u'{}_alt'.format(playlistName)
            self.startPlaylistBare(altPlaylistName, room)
        except:
            try:
                self.startPlaylistBare(playlistName, room)
            except:
                self.logger.error("Problem playing playlist '{}'".format(playlistName))
                return
        
        self.disconnect()

    def playTrackNb(self, trackNb, room):
        self.logger.debug("Playing track {:d}".format(trackNb))
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
            
            self.logger.debug("Playing track with index {:d}".format(trackIndex))
            self.client.play(trackIndex)

        except:
            self.logger.error("Problem playing track number '{:d}' (track index: {:d}, queue size: {:d})".format(trackNb, trackIndex, self.queueSize))
            return    
        
        self.disconnect()
        
    def togglePlayPause(self, room):        
        self.logger.debug("Toggling play/pause")
        self.connect()
        
        try:
            currentState = None
            currentState = self.client.status()['state']
            
            # Make sure we won't go deaf right now
            self.soundCheck(room)
            
            if currentState == 'play':
                self.logger.debug("Pausing playback")
                self.client.pause()
                self.cancelOffsetStartPlaylist = True
            else:
                self.logger.debug("Resuming playback")
                self.client.play()
        except:
            self.logger.error("Problem toggling play/pause (current state: {})".format(currentState))
        
        self.disconnect()
        
    def skipToNext(self, room):
        self.logger.debug("Skipping to next track")
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
        self.logger.debug("Skipping to previous track")
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
        self.logger.debug("Adjusting volume")
        self.connect()
        
        try:
            oldVol = None
            newVol = None
            volumeDelta = int(round(volumeDelta))
            volumeDelta *= 2
            
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
                self.logger.debug("Setting volume to {:d} [used to be {:d}]".format(newVol, oldVol))
                self.client.setvol(newVol)
            newVol = int(self.client.status()['volume'])
        except:
            self.logger.error("Problem adjusting volume (old volume: {:d}, new volume: {:d}, delta: {:d})".format(oldVol, newVol, volumeDelta))

        self.disconnect()
        
    def soundCheck(self, room):
        #self.connect()
        if not self.connected:
            return

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

        #self.disconnect()

    def isCurrentlyPlaying(self, room):
        self.logger.debug("Returning play status")
        self.connect()
        
        try:
            currentState = None
            currentState = self.client.status()['state']
            
            isCurrentlyPlaying = currentState == 'play'
        except:
            self.logger.error("Problem determining play status (current state: {})".format(currentState))
            isCurrentlyPlaying = False
        
        self.disconnect()
        
        return isCurrentlyPlaying
    
    def importPlaylist(self, playlistName, room, overwrite=False):
        self.logger.debug("Importing playlist files")
        
        try:
            self.logger.debug("Define Playlist object")
            playlist = Playlist(playlistName)
            
            self.logger.debug("Read JSON")
            playlist.readFromFile(u'playlists/{}.json'.format(playlistName))
            
            self.logger.debug(u'Playlist {}'.format(playlist.name))
                
            self.logger.debug("Copying files")
            playlist.copyFiles(u'music', u'toma', u'', overwrite, False, self.logger)
                
        except:
            self.logger.error("Error while importing playlist '{}'".format(playlistName))
    
        self.logger.debug("Adding playlist")
        
        self.connect()
        
        try:      
            self.logger.debug("Updating music library")
            self.client.update()

            self.logger.debug("Clearing playlist")
            self.client.clear()
            self.logger.debug("Initializing playlist")
            #playlistNameTmp = playlistName + '_tmp'
            #self.logger.debug("Deleting possibly existing playlist {}".format(playlistNameTmp))
            self.logger.debug("Deleting possibly existing playlist {}".format(playlistName))
            try:
                #self.client.rm(playlistNameTmp)
                self.client.rm(playlistName)
            except:
                pass
            
            #for track in playlist.tracks:
            for track, info in sorted(playlist.tracks.items(), key=lambda t: int(t[0])):
                self.logger.debug("Adding track {:d}".format(int(track)))
                #artist = playlist.tracks[track][u'artist']
                #album = playlist.tracks[track][u'album']
                #title = playlist.tracks[track][u'title']
                artist = info[u'artist']
                album = info[u'album']
                title = info[u'title']
                trackNb = int(track)

                ###self.client.findadd(u'artist', artist, u'album', album, u'title', title, u'track', track)
                ##self.client.searchaddpl(playlistNameTmp, u'artist', artist, u'album', album, u'title', title, u'track', trackNb)
                #self.client.searchaddpl(playlistName, u'artist', artist, u'album', album, u'title', title, u'track', trackNb)
                #self.client.findadd(u'artist', artist, u'album', album, u'title', title, u'track', trackNb)
                self.logger.debug(u"Adding track to playlist: artist '{}', album '{}', title '{}'".format(artist, album, title))
                self.client.findadd(u'artist', artist, u'album', album, u'title', title)

            self.client.save(playlistName)

        except:
            self.logger.error("Problem adding playlist '{}'".format(playlistName))
            raise
            return
        
        self.disconnect()            
            
    def importAllPlaylists(self, room, overwrite=False):
        self.logger.debug("Importing all playlists")
        
        try:
            playlistBasename = u'zCharliebert_'
            
            for bank in ('A', 'B', 'C', 'D'):
                for nb in range(1, 13):             
                    playlistName = u'{}{}{:02d}'.format(playlistBasename, bank, nb)
                    self.importPlaylist(playlistName, room, overwrite)
                    #return

        except:
            self.logger.error("Problem importing playlists")
            raise


if __name__ == '__main__':
    # Logging
#    logging.basicConfig(filename='sonosInterface.log', 
#                        level=logging.DEBUG, 
#                        format='%(asctime)s %(name)s %(levelname)s:%(message)s', 
#                        datefmt='%Y-%m-%d %H:%M:%S')
    logFormatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(pathname)s:%(lineno)d) %(message)s')
    logFile = 'mpdInterface.log'
    logHandler = RotatingFileHandler(logFile, mode='a', maxBytes=5*1024*1024, 
                                     backupCount=2, encoding=None, delay=0)
    logHandler.setFormatter(logFormatter)
    logHandler.setLevel(logging.DEBUG)
    logger = logging.getLogger('root')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logHandler)    
        
    logger.info("Creating instance of MpdInterface") 
    mi = MpdInterface(logger)
    try:
        #mi.importPlaylist('zCharliebert_A04', 'Office')
        #import sys
        #sys.exit()

        mi.importAllPlaylists('Office')
        import sys
        sys.exit()

        mi.importPlaylist('zCharliebert_A01', 'Office')
        mi.importPlaylist('zCharliebert_A02', 'Office')
        mi.importPlaylist('zCharliebert_A03', 'Office')
        mi.importPlaylist('zCharliebert_A04', 'Office')
        mi.importPlaylist('zCharliebert_A05', 'Office')
        mi.importPlaylist('zCharliebert_A06', 'Office')
        mi.importPlaylist('zCharliebert_A07', 'Office')
        mi.importPlaylist('zCharliebert_A08', 'Office')
        mi.importPlaylist('zCharliebert_A09', 'Office')
        mi.importPlaylist('zCharliebert_A10', 'Office')
        mi.importPlaylist('zCharliebert_A11', 'Office')
        mi.importPlaylist('zCharliebert_A12', 'Office')
        mi.importPlaylist('zCharliebert_B01', 'Office')
        mi.importPlaylist('zCharliebert_B02', 'Office')
        mi.importPlaylist('zCharliebert_B03', 'Office')
        mi.importPlaylist('zCharliebert_B04', 'Office')
        mi.importPlaylist('zCharliebert_B05', 'Office')
        mi.importPlaylist('zCharliebert_B06', 'Office')
        mi.importPlaylist('zCharliebert_B07', 'Office')
        mi.importPlaylist('zCharliebert_B08', 'Office')
        mi.importPlaylist('zCharliebert_B09', 'Office')
        mi.importPlaylist('zCharliebert_B10', 'Office')
        mi.importPlaylist('zCharliebert_B11', 'Office')
        mi.importPlaylist('zCharliebert_B12', 'Office')
        mi.importPlaylist('zCharliebert_C01', 'Office')
        mi.importPlaylist('zCharliebert_C02', 'Office')
        mi.importPlaylist('zCharliebert_C03', 'Office')
        mi.importPlaylist('zCharliebert_C04', 'Office')
        mi.importPlaylist('zCharliebert_C05', 'Office')
        mi.importPlaylist('zCharliebert_C06', 'Office')
        mi.importPlaylist('zCharliebert_C07', 'Office')
        mi.importPlaylist('zCharliebert_C08', 'Office')
        mi.importPlaylist('zCharliebert_C09', 'Office')
        mi.importPlaylist('zCharliebert_C10', 'Office')
        mi.importPlaylist('zCharliebert_C11', 'Office')
        mi.importPlaylist('zCharliebert_C12', 'Office')
        mi.importPlaylist('zCharliebert_D01', 'Office')
        mi.importPlaylist('zCharliebert_D02', 'Office')
        mi.importPlaylist('zCharliebert_D03', 'Office')
        mi.importPlaylist('zCharliebert_D04', 'Office')
        mi.importPlaylist('zCharliebert_D05', 'Office')
        mi.importPlaylist('zCharliebert_D06', 'Office')
        mi.importPlaylist('zCharliebert_D07', 'Office')
        mi.importPlaylist('zCharliebert_D08', 'Office')
        mi.importPlaylist('zCharliebert_D09', 'Office')
        mi.importPlaylist('zCharliebert_D10', 'Office')
        mi.importPlaylist('zCharliebert_D11', 'Office')
        mi.importPlaylist('zCharliebert_D12', 'Office')
        import sys
        sys.exit()
        
        
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
        
