import logging
from logging.handlers import RotatingFileHandler
from time import sleep
import time
import json
import io
import os
import re
from smb.SMBConnection import SMBConnection

class Playlist:
    def __init__(self, name):
        self.name = name
        self.tracks = dict()
        
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4, ensure_ascii=False)
        
    def addTrack(self, trackNb, artist, album, title, uri):
        self.tracks[trackNb] = dict()
        t = self.tracks[trackNb]

        t[u'artist'] = artist
        t[u'album'] = album
        t[u'title'] = title
        t[u'uri'] = uri
        
    def writeToFile(self, filename):
        
        with io.open(filename, 'w', encoding='utf8') as outfile:
#             data = json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4, ensure_ascii=False)
            data = self.toJSON()
            outfile.write(unicode(data))
             
#         with open(filename, 'w') as outfile:
#             json.dump(self, outfile, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def readFromFile(self, filename):
        
#         logger.debug(u'readFromFile {}'.format(filename))
        with open(filename) as json_data:
#             self = json.load(json_data)
#             logger.debug(u'Opened file {}'.format(filename))
            data = json.load(json_data)
 
#             logger.debug(u'Setting name')
            self.name = data[u'name']
#             logger.debug(u'Setting tracks')
            self.tracks = data[u'tracks']
#             logger.debug(u'All set')

    def copyFiles(self, destDir, user, password, overwrite=False, logger=None):
        try:
            os.mkdir(destDir)
        except OSError:
            pass
        
        try:
            for track in self.tracks:
                file = self.tracks[track][u'uri']
                m = re.search(u'//([^/]+)/([^/]+)/(.+)\s*$', file)
                
                if logger is not None:
                    logger.debug(u'group 1 = {}\ngroup 2 = {}\ngroup 3 = {}'.format(m.group(1), m.group(2), m.group(3)))
        
                server = u'{}.local'.format(m.group(1))
                share = u'{}'.format(m.group(2))
                path = u'{}'.format(m.group(3))
                target= u'{}'.format(m.group(3))
                
                if logger is not None:
                    logger.debug(u'server = {}\nshare = {}\npath = {}\ntarget = {}'.format(server, share, path, target))
                
                if logger is not None:
                    logger.debug(u'Determining target file using additional dir \'{}\''.format(destDir))
                
                target = os.path.join(destDir, target)
                
                if os.path.isfile(target) and not overwrite:
                    continue
                
                dir = os.path.dirname(target)

                if logger is not None:
                    logger.debug(u'Target file: \'{}\''.format(target))
                    logger.debug(u'Dirname: \'{}\''.format(dir))
        
                try:
                    os.makedirs(dir)
                except OSError:
                    pass

                if logger is not None:
                    logger.debug(u'Converting strings')
                                    
                user = user.encode('utf8', 'ignore')
                password = password.encode('utf8', 'ignore')
                server = server.encode('utf8', 'ignore')
                share = share.encode('utf8', 'ignore')    
                
                conn = SMBConnection(user, password, server, server, use_ntlm_v2 = True)
                assert conn.connect(server, 139)
                
                if logger is not None:
                    logger.debug(u'Connection established, retrieving file')
        
                with open(target, 'wb') as fp:
                    conn.retrieveFile(share, path, fp)
                
                if logger is not None:
                    logger.debug(u'File retrieved')
                    
                conn.close()
        except:
            if logger is not None:
                logger.error("user = {}\npassword = {}\nserver = {}\nshare = {}\ntarget = {}".format(user, password, server, share, target))

    
class PlayerInterface():
    def __init__(self, logger):
        # Logging mechanism
        self.logger = logger
        
        # Flag indicating the status of the connection to the music system server
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
        self.minTimePlaylist = 30 # (seconds) Time before starting another playlist is allowed
        self.timeLastStartPlaylist = time.time() - self.minTimePlaylist # Make sure we can start a playlist right away
        self.cancelOffsetStartPlaylist = False # True if the playlist has been stopped before the end of the offset time
        
    def connect(self): 
        # Connection status (Off by default)
        self.logger.debug("connect")
        self.connected = False
        
    def printSpeakerList(self):
        self.logger.debug("printSpeakerList")
        print("Speaker: None")
    
    def prepareRoom(self, room):
        self.logger.debug("prepareRoom")
        return True
                        
    def getSpeaker(self, room):
        self.logger.debug("getSpeaker")
        return None

    def offsetStartPlaylist(self, playlistName):
        self.logger.debug("offsetStartPlaylist")
        currentTime = time.time()
        self.logger.debug("offsetStartPlaylist: {} s since the last playlist command".format(currentTime - self.timeLastStartPlaylist))
        
        if currentTime - self.timeLastStartPlaylist < self.minTimePlaylist:
            self.logger.debug("Discarding command to start playlist {} (issued {} s after the last playlist command)".format(playlistName, currentTime - self.timeLastStartPlaylist))
            return True
        
        self.logger.debug("offsetStartPlaylist: Allowing start playlist command".format(currentTime - self.timeLastStartPlaylist))
        
        self.timeLastStartPlaylist = currentTime
        self.cancelOffsetStartPlaylist = False
        return False
        
    def startPlaylist(self, playlistName, room):
        self.logger.debug("startPlaylist")
        # Discard commands that are issued too briefly after the last
        if not self.cancelOffsetStartPlaylist and self.offsetStartPlaylist(playlistName):
            return
        
        self.cancelOffsetStartPlaylist = False

    def playTrackNb(self, trackNb, room):
        self.logger.debug("playTrackNb")
        if trackNb < 1:
            self.logger.error("Cannot play track number {:d}".format(trackNb))
            return 
        
        trackIndex = self.indexBegPlaylist + trackNb - 1
        
        if trackIndex >= self.queueSize:
            self.logger.error("Track number {:d} too large (index: {:d}, playlist size: {:d})".format(trackNb, trackIndex, self.playlistSize))
            return
          

    def togglePlayPause(self, room):
        self.logger.debug("togglePlayPause")

    def skipToNext(self, room):
        self.logger.debug("skipToNext")
          
    def skipToPrevious(self, room):
        self.logger.debug("skipToPrevious")
          
    def adjustVolume(self, volumeDelta, room):
        self.logger.debug("adjustVolume")
        
    def soundCheck(self, room):
        self.logger.debug("soundCheck")
        vol = -1
        newVol = -1

    # Returns True in case the currently selected player is currently playing
    def isCurrentlyPlaying(self, room):
        self.logger.debug("isCurrentlyPlaying")
        return False
    
    # Obtain the details of a given playlist and save those to a file
    def exportPlaylistDetails(self, playlistName, room):
        self.logger.debug("exportPlaylistDetails")
        
    # Reads the details of a given playlist and save those in the player configuration
    def importPlaylistDetails(self, playlistName, room):
        self.logger.debug("importPlaylistDetails")

if __name__ == '__main__':
    # Logging
    logFormatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(pathname)s:%(lineno)d) %(message)s')
    logFile = 'playerInterface.log'
    logHandler = RotatingFileHandler(logFile, mode='a', maxBytes=5*1024*1024, 
                                     backupCount=2, encoding=None, delay=0)
    logHandler.setFormatter(logFormatter)
    logHandler.setLevel(logging.DEBUG)
    logger = logging.getLogger('root')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logHandler)    
        
    logger.info("Creating instance of PlayerInterface") 
    pi = PlayerInterface(logger)
    try:
        pi.printSpeakerList()
        pi.startPlaylist("zCharliebert_A01", "Office")
        sleep(5)
        pi.playTrackNb(3, "Office")
        sleep(5)
        pi.startPlaylist("zCharliebert_A02", "Office")
        sleep(5)
        pi.playTrackNb(3, "Office")
        sleep(5)
        pi.togglePlayPause("Office")
        sleep(5)
        pi.togglePlayPause("Office")
        sleep(5)
        pi.skipToNext("Office")
        sleep(5)
        pi.skipToNext("Office")
        sleep(5)
        pi.skipToPrevious("Office")
        sleep(5)
        pi.skipToPrevious("Office")
        sleep(5)
        pi.adjustVolume(10, "Office")
        sleep(5)
        pi.adjustVolume(10, "Office")
        sleep(5)
        pi.adjustVolume(-10, "Office")
        sleep(5)
        pi.adjustVolume(-10, "Office")
    except KeyboardInterrupt:
        logger.info("Stop (Ctrl-C from __main__)") 
        print("Stop (Ctrl-C) [from main]")
        
