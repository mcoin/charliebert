import soco
import logging

class SonosInterface():
    def __init__(self):
        # Prepare info about sonos speakers
        list_sonos = list(soco.discover())
    
        self.speakers = {}
        self.names = []
    
        for speaker in list_sonos:
            name = speaker.get_speaker_info()['zone_name']
            self.names.append(name)
            self.speakers[name] = speaker
        
    def printSpeakerList(self):
        for name, speaker in self.speakers.items():
            print("Speaker: {}".format(name))
            
    def startPlaylist(self, playlistName, room):
        if room not in self.names:
            logging.error("Room '{}' not available in the sonos system".format(room))
            return
        
        playlists = self.speakers[room].get_sonos_playlists()
        self.speakers[room].clear_queue()
        self.speakers[room].add_to_queue(playlists[-1])
        self.speakers[room].play()
        
if __name__ == '__main__':
    # Logging
    logging.basicConfig(filename='sonosInterface.log', 
                        level=logging.DEBUG, 
                        format='%(asctime)s %(name)s %(levelname)s:%(message)s', 
                        datefmt='%Y-%m-%d %H:%M:%S')
        
    logging.info("Creating instance of SonosInterface") 
    si = SonosInterface()
    try:
        si.printSpeakerList()
        si.startPlaylist("dummy", "Office")
    except KeyboardInterrupt:
        logging.info("Stop (Ctrl-C from __main__)") 
        print("Stop (Ctrl-C) [from main]")
        