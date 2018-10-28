import logging
from logging.handlers import RotatingFileHandler
from sonosInterface import SonosInterface
from playerInterface import Playlist
import subprocess
import os
import filecmp
import json
from shutil import copyfile
    
from PIL import Image
import numpy as np
import operator

class ExtractCovers():
    def __init__(self, logger):
        # Logging mechanism
        self.logger = logger
        
        # Parameters
        self.importPlaylists = True
        self.extractCoverArt = True
        self.removeFiles = True
        self.regeneratePlaylistImage = True
        self.pdflatexPath = u'/opt/local/bin/pdflatex'
        self.mp4artPath = u'/opt/local/bin/mp4art'
        self.ffmpegPath = u'/usr/local/bin/ffmpeg'
        
        self.playlistKeyTex='''
    \\documentclass[border=10pt]{standalone} 
    \\usepackage{verbatim}
    
    %\\newcommand{\\includegraphicsmaybe}[1]{\\IfFileExists{#1}{\\includegraphics{#1}}{}}}
    
    \\newcommand{\\playlistIndex}{placehoder_index}
    \\newcommand{\\playlistName}{zCharliebert_\\playlistIndex} 
    
    \\usepackage{ifthen}
    \\usepackage{tikz}
    
    \\begin{document}
    \\begin{tikzpicture}
    
      \\draw[rounded corners=8pt,very thick] (-1,-0.5) rectangle (9,13.5);
    
      \\filldraw[fill=black,very thick]    (0.5,12.5) circle (0.75);
    
      \\ifthenelse{\\equal{\\playlistIndex}{A}}{
        \\filldraw[fill=red,very thick]    (3.75,12.5) circle (0.5);
      }{
        \\draw[very thick]    (3.75,12.5) circle (0.5);
      }
      \\ifthenelse{\\equal{\\playlistIndex}{B}}{
        \\filldraw[fill=green,very thick]    (5,12.5) circle (0.5);
      }{
        \\draw[very thick]    (5,12.5) circle (0.5);
      }
      \\ifthenelse{\\equal{\\playlistIndex}{C}}{
        \\filldraw[fill=orange,very thick]    (6.25,12.5) circle (0.5);
      }{
        \\draw[very thick]    (6.25,12.5) circle (0.5);
      }
      \\ifthenelse{\\equal{\\playlistIndex}{D}}{
        \\filldraw[fill=yellow,very thick]    (7.5,12.5) circle (0.5);
      }{
        \\draw[very thick]    (7.5,12.5) circle (0.5);
      }
    
    
      \\filldraw[fill=yellow,rounded corners=8pt,very thick] (0,9) rectangle (2,11);
      \\filldraw[fill=red,very thick]    (4,10) circle (1);
      \\filldraw[fill=green,rounded corners=8pt,very thick]  (6,9) rectangle (8,11);
    
      \\filldraw[fill=blue,very thick]   (1,7) circle (1);
      \\filldraw[fill=black,rounded corners=8pt,very thick]  (3,6) rectangle (5,8);
      \\filldraw[fill=yellow,very thick] (7,7) circle (1);
    
      \\filldraw[fill=red,rounded corners=8pt,very thick]    (0,3) rectangle (2,5);
      \\filldraw[fill=green,very thick]  (4,4) circle (1);
      \\filldraw[fill=blue,rounded corners=8pt,very thick]   (6,3) rectangle (8,5);
    
      \\filldraw[fill=blue,very thick]   (1,1) circle (1);
      \\filldraw[fill=yellow,rounded corners=8pt,very thick] (3,0) rectangle (5,2);
      \\filldraw[fill=red,very thick]    (7,1) circle (1);
    
    
      \\node[inner sep=0pt] (\\playlistIndex01) at (1.33,10.33)
        {\\IfFileExists{\\playlistName01.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName01.jpg}}{}};
      \\node[inner sep=0pt] (\\playlistIndex02) at (4.33,10.33)
        {\\IfFileExists{\\playlistName02.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName02.jpg}}{}};
      \\node[inner sep=0pt] (\\playlistIndex03) at (7.33,10.33)
        {\\IfFileExists{\\playlistName03.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName03.jpg}}{}};
    
      \\node[inner sep=0pt] (\\playlistIndex04) at (1.33,7.33)
        {\\IfFileExists{\\playlistName04.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName04.jpg}}{}};
      \\node[inner sep=0pt] (\\playlistIndex05) at (4.33,7.33)
        {\\IfFileExists{\\playlistName05.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName05.jpg}}{}};
      \\node[inner sep=0pt] (\\playlistIndex06) at (7.33,7.33)
        {\\IfFileExists{\\playlistName06.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName06.jpg}}{}};
    
      \\node[inner sep=0pt] (\\playlistIndex07) at (1.33,4.33)
        {\\IfFileExists{\\playlistName07.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName07.jpg}}{}};
      \\node[inner sep=0pt] (\\playlistIndex08) at (4.33,4.33)
        {\\IfFileExists{\\playlistName08.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName08.jpg}}{}};
      \\node[inner sep=0pt] (\\playlistIndex09) at (7.33,4.33)
        {\\IfFileExists{\\playlistName09.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName09.jpg}}{}};
    
      \\node[inner sep=0pt] (\\playlistIndex10) at (1.33,1.33)
        {\\IfFileExists{\\playlistName10.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName10.jpg}}{}};
      \\node[inner sep=0pt] (\\playlistIndex11) at (4.33,1.33)
        {\\IfFileExists{\\playlistName11.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName11.jpg}}{}};
      \\node[inner sep=0pt] (\\playlistIndex12) at (7.33,1.33)
        {\\IfFileExists{\\playlistName12.jpg}{\\includegraphics[width=.16\\textwidth]{\\playlistName12.jpg}}{}};
    
    \\end{tikzpicture}
    \\end{document}
    '''
    
        self.playlistKeysTex='''
    \\documentclass{article}
    \\usepackage{graphicx}
    \\usepackage{subcaption}
    \\usepackage[a4paper, 
     total={190mm,277mm},
     left=10mm,
     top=20mm,
    ]{geometry}
    \\begin{document}
    \\thispagestyle{empty}
    \\begin{figure}
    \\begin{subfigure}{.5\\textwidth}
      \\centering
      \\includegraphics[width=.8\\linewidth]{zCharliebert_A.pdf}
      %\\caption{A}
    \\end{subfigure}%
    \\begin{subfigure}{.5\\textwidth}
      \\centering
      \\includegraphics[width=.8\\linewidth]{zCharliebert_B.pdf}
      %\\caption{B}
    \\end{subfigure}
    
    \\begin{subfigure}{.5\\textwidth}
      \\centering
      \\includegraphics[width=.8\\linewidth]{zCharliebert_C.pdf}
      %\\caption{A}
    \\end{subfigure}%
    \\begin{subfigure}{.5\\textwidth}
      \\centering
      \\includegraphics[width=.8\\linewidth]{zCharliebert_D.pdf}
      %\\caption{B}
    \\end{subfigure}\\\\
    \\end{figure}
    \\end{document}
    '''
    
    def pil_grid(self, images, max_horiz=np.iinfo(int).max):
        maxHeight = 0
        maxWidth = 0
        for img in images:
            maxWidth = max(maxWidth, img.size[0])
            maxHeight = max(maxHeight, img.size[1])
        maxLength = max(maxWidth, maxHeight)
        size = (maxLength, maxLength)
        
        resizedImages = []
        imageOffset = []
        for img in images:
            newWidth = 0
            newHeight = 0
            hOffset = 0
            vOffset = 0
            if img.size[0] > img.size[1]:
                newWidth = maxLength
                newHeight = img.size[1] * maxLength / img.size[0]
                hOffset = 0
                vOffset = (maxLength - newHeight)/2
            else:
                newHeight = maxLength
                newWidth = img.size[0] * maxLength / img.size[1]
                vOffset = 0
                hOffset = (maxLength - newWidth)/2            
                
            resizedImages.append(img.resize((newWidth, newHeight)))
            imageOffset.append((hOffset, vOffset))
        
        n_images = len(resizedImages)
        n_horiz = min(n_images, max_horiz)
        n_vert = n_images // n_horiz
        
        h_size, v_size = n_horiz * maxLength, n_vert * maxLength        
        im_grid = Image.new('RGB', (h_size, v_size), color='white')
        for i, im in enumerate(resizedImages):
            im_grid.paste(im, ((i % n_horiz) * maxLength + imageOffset[i][0], (i // n_vert) * maxLength + imageOffset[i][1]))
        return im_grid
    
    def createPlaylistKey(self):
        importPlaylists = True
        extractCoverArt = True
        removeFiles = True
        
        self.regeneratePlaylistImage = True
        pdflatexPath = u'/opt/local/bin/pdflatex'
        mp4artPath = u'/opt/local/bin/mp4art'
        ffmpegPath = u'/usr/local/bin/ffmpeg'
            
        logger.info("Creating instance of SonosInterface") 
        si = SonosInterface(logger)
        try:
            si.printSpeakerList()        
            
            playlistBasename = u'zCharliebert_'
            
            for bank in (u'A', u'B', u'C', u'D'):
            #for bank in (u'A'):
                for index in range(1,13):
                #for index in range(1,2):
                    playlistChanged = True
                    playlistName = u'{}{}{:02d}'.format(playlistBasename, bank, index)
                    if self.importPlaylists:
                        try:                            
                            logger.debug(u'Remove existing file {}_prev.json'.format(playlistName))
                            os.remove(u'playlists/{}_prev.json'.format(playlistName))
                        except:
                            pass
                            
                        if os.path.isfile(u'playlists/{}.json'.format(playlistName)):                            
                            logger.debug(u'Make a copy of existing file {}.json'.format(playlistName))
                            copyfile(u'playlists/{}.json'.format(playlistName), u'playlists/{}_prev.json'.format(playlistName))
                                
                        si.exportPlaylistDetails(playlistName, 'Office', None, True)
                     
                        try:
                            if (filecmp.cmp(u'playlists/{}.json'.format(playlistName), u'playlists/{}_prev.json'.format(playlistName))):
                                logger.debug(u'Playlist file identical to previous version (playlists/{}.json same as playlists/{}_prev.json)'.format(playlistName, playlistName))
                                playlistChanged = False
                            else:
                                logger.debug(u'Playlist file not identical to previous version (playlists/{}.json differs from playlists/{}_prev.json)'.format(playlistName, playlistName))
                        except:
                            pass
                        
                        if playlistChanged or not os.path.isfile(u'playlists/{}.jpg'.format(playlistName)):
                            logger.debug(u'Playlist {} has changed and/or playlist image not present: Regenerating'.format(playlistName))
                            playlistChanged = True
                        else:
                            logger.debug(u'Playlist {} unchanged and playlist image present: Not regenerating'.format(playlistName))
                            
                        if playlistChanged:
                            try:
                                logger.debug("Define Playlist object")
                                playlist = Playlist(playlistName)                        
            
                                logger.debug("Read JSON")
                                playlist.readFromFile(u'playlists/{}.json'.format(playlistName))
                                  
                                logger.debug(u'Playlist {}'.format(playlist.name))
                                      
                                logger.debug("Copying files")
                                playlist.copyFiles(u'playlists/{}'.format(playlistName), u'toma', u'', True, True, logger)
                            except:
                                logger.error("Error while importing playlist '{}'".format(playlistName))    
                    
                    if playlistChanged:
                        if self.extractCoverArt:
                            try:
                                path = os.path.join(os.getcwd(), u'playlists/{}'.format(playlistName))                    
    
                                files = os.listdir(path)
                                  
                                for file in files:
                                    fileAbs = os.path.join(path, file)
                                    fileNameAbs, fileExtension = os.path.splitext(fileAbs)
                                    try:
                                        if fileExtension == u'.jpg' or fileExtension == u'.png':
                                            os.remove(fileAbs)
                                    except:
                                        pass
                                
                                files = os.listdir(path)
                                  
                                for file in files:
                                    fileAbs = os.path.join(path, file)
                                    fileNameAbs, fileExtension = os.path.splitext(fileAbs)
                                    try:
                                        if fileExtension == u'.m4a':
                                            subprocess.check_call([mp4artPath, u'--extract', fileAbs])
                                            if self.removeFiles:
                                                os.remove(fileAbs)
                                        elif fileExtension == u'.mp3':
                                            subprocess.check_call([ffmpegPath, u'-i', fileAbs, u'-an', u'-vcodec', u'copy', u'{}.jpg'.format(fileNameAbs)])
                                            if self.removeFiles:
                                                os.remove(fileAbs)
                                    except:
                                        logger.error("Error while extracting cover art for file '{}' in playlist '{}'".format(file, playlistName))    
                            except:
                                logger.error("Error while extracting cover art for playlist '{}'".format(playlistName))    
                    
                    if playlistChanged or self.regeneratePlaylistImage:                        
                        try:
                            path = os.path.join(os.getcwd(), u'playlists/{}'.format(playlistName))                    
                            files = os.listdir(path)
                            imgList = dict()
                             
                            for file in files:
                                fileAbs = os.path.join(path, file)
                                fileNameAbs, fileExtension = os.path.splitext(fileAbs)
                                try:
                                    if fileExtension in (u'.jpg', u'.png'):
                                        alreadyInList = False
                                        for img in imgList.keys():
                                            if (filecmp.cmp(fileAbs, img)):
                                                alreadyInList = True
                                                imgList[img] += 1
                                                break
                                        if not alreadyInList:
                                            imgList[fileAbs] = 1
                                             
                                except:
                                    logger.error("Error while processing cover art file '{}' in playlist '{}'".format(file, playlistName))
                                 
                            with open(u'playlists/{}/images.txt'.format(playlistName), 'w') as file:
                                file.write(json.dumps(imgList))
                            
                            try:
                                os.remove(u'playlists/{}.jpg'.format(playlistName))
                            except:
                                pass
                            
                            # Sort cover images according to frequency
                            sorted_images = sorted(imgList.items(), key=operator.itemgetter(1))
                            images = []
                            weights = []
                            weightFirst = None
                            for i in reversed(sorted_images):
                                images.append(Image.open(i[0]))
                                if (weightFirst is None):
                                    weightFirst = float(i[1])
                                weights.append(float(i[1])/weightFirst)
                            
                            if len(imgList) >= 4 and weights[3] > 0.05:
                                cover = self.pil_grid((images[0], images[1], images[2], images[3]), 2)
                            elif len(imgList) >= 3 and weights[2] > 0.1:
                                cover = self.pil_grid((images[0], images[1], images[2], images[0]), 2)
                            elif len(images) >= 2 and weights[1] > 0.1:
                                cover = self.pil_grid((images[0], images[1], images[1], images[0]), 2)
                            elif len(images) > 0:
                                cover = images[0]
                            else:
                                #cover = Image.new('RGB', (100, 100), color='white')
                                cover = None
                                
                            if cover is not None:
                                cover.save(u'playlists/{}.jpg'.format(playlistName), "JPEG", quality=80)
                                 
                        except:
                            logger.error("Error while grouping cover art for playlist '{}'".format(playlistName))    
        
            logger.debug("Creating playlist key illustration")
            wd = os.path.join(os.getcwd(), u'playlists')
            for bank in (u'A', u'B', u'C', u'D'):
                playlistKey = u'{}{}'.format(playlistBasename, bank)            
                texFile = os.path.join(wd, u'{}.tex'.format(playlistKey))
                
                with open(texFile, 'w') as key:
                    key.write(self.playlistKeyTex.replace(u'placehoder_index', bank))
                subprocess.check_call([pdflatexPath, texFile], cwd=wd)
                
            wd = os.path.join(os.getcwd(), u'playlists')
            texFile = os.path.join(wd, u'{}.tex'.format(playlistBasename))
            
            with open(texFile, 'w') as keys:
                keys.write(self.playlistKeysTex)
            subprocess.check_call([pdflatexPath, texFile], cwd=wd)
            
        except KeyboardInterrupt:
            logger.info("Stop (Ctrl-C from __main__)") 
            print("Stop (Ctrl-C) [from main]")
                            

if __name__ == '__main__':
    logFormatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(pathname)s:%(lineno)d) %(message)s')
    logFile = 'extractCovers.log'
    logHandler = RotatingFileHandler(logFile, mode='a', maxBytes=5*1024*1024, 
                                     backupCount=2, encoding=None, delay=0)
    logHandler.setFormatter(logFormatter)
    logHandler.setLevel(logging.DEBUG)
    logger = logging.getLogger('root')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logHandler)    
    
    extractCovers = ExtractCovers(logger)
    
    try:
        extractCovers.createPlaylistKey()
    except KeyboardInterrupt:
        logger.info("Stop (Ctrl-C from __main__)") 
        print("Stop (Ctrl-C) [from main]")