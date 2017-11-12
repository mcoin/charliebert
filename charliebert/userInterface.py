#!/usr/bin/env python3.4
import RPi.GPIO as GPIO 
from collections import deque
import threading
from time import sleep
import time
import logging
from logging.handlers import RotatingFileHandler
from distutils.cmd import Command
import smbus
    
    
class UserInterface:
    
    def __init__(self, logger):
        self.logger = logger
        self.logger.info("Initializing instance of UserInterface")
        
        # GPIO settings
        GPIO.setwarnings(True)
        GPIO.setmode(GPIO.BCM)
        
        # Switches
        self.logger.debug("Setting up switches")
        self.initSwitches()
        
        # LEDs
        self.logger.debug("Setting up LEDs")
        self.initLeds()
    
        # Rotary encoder
        self.logger.debug("Setting up rotary encoder")
        self.initRotaryEncoder()
    
        self.stopper = None
        
        # Break the main loop if marked True
        self.stopRequested = False
        
        # Event queue to trigger actions from the server
        self.queue = None
        
        # Number of operations (key presses): Incremented after each key press
        self.nbOperations = 0
        # Control counters
        self.switchOffCurrentNbOperations = 0
        self.activateAltModeCurrentNbOperations = 0
                
        # Indicator for shift mode: if true, blink all bank leds
        self.blinking = False
        # Period for blinking leds (in seconds)
        self.blinkPeriod = 0.5
        
        # SMBUS stuff for additional ports via MCP23017 chip
        self.initMcp()
        self.currentRoomNb = None

        
    def initMcp(self):
        self.mcpDeviceAddress = 0x20
        self.mcpAddressMap = {
    0x00: 'IODIRA', 0x01: 'IODIRB', 0x02: 'IPOLA', 0x03: 'IPOLB',
    0x04: 'GPINTENA', 0x05: 'GPINTENB', 0x06: 'DEFVALA', 0x07: 'DEVFALB',
    0x08: 'INTCONA', 0x09: 'INTCONB', 0x0a: 'IOCON', 0x0b: 'IOCON',
    0x0c: 'GPPUA', 0x0d: 'GPPUB', 0x0e: 'INTFA', 0x0f: 'INTFB',
    0x10: 'INTCAPA', 0x11: 'INTCAPB', 0x12: 'GPIOA', 0x13: 'GPIOB',
    0x14: 'OLATA', 0x15: 'OLATB'}
        self.mcpRegisterMap = {value: key for key, value in self.mcpAddressMap.iteritems()}
        self.roomNbMap = {
                        0xFB: 1, 0xF7: 2, 0xEF: 3, 0xDF: 4, 0xFE: 5, 0xFD: 6
                        }
        
        # Define device
        self.mcpBus = smbus.SMBus(1)
        # Set pullup resistors
        self.mcpBus.write_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap['GPPUA'], 0xFF)
        self.mcpBus.write_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap['GPPUB'], 0xFF)
        # Set direction (input) 
        self.mcpBus.write_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap['IODIRA'], 0xFF)
        self.mcpBus.write_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap['IODIRB'], 0xFF)
    
    def readMcp(self, reg):
        #self.logger.debug("readMcp for reg = {}".format(reg))
        if reg in self.mcpRegisterMap:
            try:
                #self.logger.debug("readMcp: reg = {} exists".format(reg))
                return self.mcpBus.read_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap[reg])
            except:
                #self.logger.debug("readMcp: Cannot read data for reg = {}".format(reg))
                raise
        else:
            #self.logger.debug("readMcp: reg = {} does not exist".format(reg))
            raise
        
    def getActiveRoomNb(self):
        #self.logger.debug("getActiveRoomNb")
        try:
            sw = self.readMcp('GPIOB')
            #self.logger.debug("sw = {}".format(sw))
            #self.logger.debug("room = {}".format(self.roomNbMap[sw]))
            return self.roomNbMap[sw]
        except:
            return "<Unknown room>"
        
    
    def initSwitches(self):
        # Switch numbers: {Port, Switch number}
        self.switchNbs = { 
                    14: 1,
                    15: 4,
                    18: 7,
                    23: 10,
                    24: 2,
                    25: 5,
                    8: 8,
                    7: 11,
                    12: 3,
                    16: 6,
                    20: 9,
                    21: 12
                    }       
        # Switches: {Port, Name}
        self.switches = { 
                    14: "Switch {:d}".format(self.switchNbs[14]),
                    15: "Switch {:d}".format(self.switchNbs[15]),
                    18: "Switch {:d}".format(self.switchNbs[18]),
                    23: "Switch {:d}".format(self.switchNbs[23]),
                    24: "Switch {:d}".format(self.switchNbs[24]),
                    25: "Switch {:d}".format(self.switchNbs[25]),
                    8:  "Switch {:d}".format(self.switchNbs[8]),
                    7:  "Switch {:d}".format(self.switchNbs[7]),
                    12: "Switch {:d}".format(self.switchNbs[12]),
                    16: "Switch {:d}".format(self.switchNbs[16]),
                    20: "Switch {:d}".format(self.switchNbs[20]),
                    21: "Switch {:d}".format(self.switchNbs[21]),
                    5:  "Play/Pause",
                    11: "Forward",
                    9:  "Back",
                    17: "Bank",
                    27: "Mode"
                    }
        # Special switches
        self.bankSwitch = "Bank" # Switch to a different playlist bank
        self.modeSwitch = "Mode" # Hold down to activate alternate mode
        self.modePort = 0 # Port for the mode switch
        self.playSwitch = "Play/Pause" # Switch to stop/resume playback
        self.forwardSwitch = "Forward" # Switch to skip forward
        self.backSwitch = "Back" # Switch to skip backward
        self.backPort = 0 # Port for the back switch
        # Checks (Bank and Mode switch must be defined)
        assert(self.bankSwitch in self.switches.values())
        assert(self.modeSwitch in self.switches.values())
        assert(self.playSwitch in self.switches.values())
        assert(self.forwardSwitch in self.switches.values())
        assert(self.backSwitch in self.switches.values())
        # Indicate whether alternate mode is on (upon holding down the Mode button)
        self.altMode = False
        # Indicate whether alternate mode 2 (shift) is on (upon holding down the Mode & Play buttons)
        self.shiftMode = False
        # Set ports as input with pull-up resistor
        for s, name in self.switches.items():
            GPIO.setup(s, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            # Mark port for the Mode switch
            if name == self.modeSwitch:
                self.modePort = s
            elif name == self.backSwitch:
                self.backPort = s                
        # Define callbacks for switch presses
        for port, name in self.switches.items():
            if name == self.bankSwitch:
                GPIO.add_event_detect(port, GPIO.FALLING, callback=self.callbackBankSwitch, bouncetime=500)
            elif name == self.modeSwitch:
                GPIO.add_event_detect(port, GPIO.BOTH, callback=self.callbackModeSwitch, bouncetime=500)
            elif port in self.switchNbs:
                GPIO.add_event_detect(port, GPIO.FALLING, callback=self.callbackSwitch, bouncetime=500)  
            else:
                GPIO.add_event_detect(port, GPIO.FALLING, callback=self.callbackControlSwitch, bouncetime=500)
                
    def initLeds(self):
        # LEDs for the different playlist banks: Ports and names
        self.ledPorts = [6, 19, 13, 26]
        self.ledNames = ["Bank A", "Bank B", "Bank C", "Bank D"]
        # State of the bank leds
        self.ledStates = deque()
        # Checks (the lists have to have the same number of elements)
        assert(len(self.ledPorts) == len(self.ledNames))
        # LEDs: {Port, Name}
        leds = dict(zip(self.ledPorts, self.ledNames))
        # Name of the LED which is ON by default at startup
        defaultLed = "Bank A"
        assert(defaultLed in self.ledNames)
        # Set the corresponding ports as output with state HIGH for the 1st one
        for l, name in leds.items():
            GPIO.setup(l, GPIO.OUT)
            GPIO.output(l, GPIO.HIGH if name == defaultLed else GPIO.LOW)
            self.ledStates.append(GPIO.HIGH if len(self.ledStates) == 0 else GPIO.LOW)


    def initRotaryEncoder(self):
        # Current volume    
        self.volume = 0                                    
        self.newCounter = 0   
        
        # Encoder input A
        self.encoderA = 10                  
        # Encoder input B
        self.encoderB = 22 
        
        self.rotaryCounter = 0  # Start counting from 0
        self.rotaryCurrentA = 1  # Assume that rotary switch is not 
        self.rotaryCurrentB = 1  # moving while we init software
        
        self.rotaryLock = threading.Lock()  # create lock for rotary switch
        
        # define the Encoder switch inputs
        GPIO.setup(self.encoderA, GPIO.IN)                 
        GPIO.setup(self.encoderB, GPIO.IN)
        # setup callback thread for the A and B encoder 
        # use interrupts for all inputs
        GPIO.add_event_detect(self.encoderA, GPIO.RISING, callback=self.rotary_interrupt)  # NO bouncetime 
        GPIO.add_event_detect(self.encoderB, GPIO.RISING, callback=self.rotary_interrupt)  # NO bouncetime 

    # Rotary encoder interrupt:
    # this one is called for both inputs from rotary switch (A and B)
    def rotary_interrupt(self, A_or_B):
        # read both switches
        Switch_A = GPIO.input(self.encoderA)
        Switch_B = GPIO.input(self.encoderB)
        # now check if state of A or B has changed
        # if not that means that bouncing caused it
        if self.rotaryCurrentA == Switch_A and self.rotaryCurrentB == Switch_B:  # Same interrupt as before (Bouncing)?
            return  # ignore interrupt!
    
        self.rotaryCurrentA = Switch_A  # remember new state
        self.rotaryCurrentB = Switch_B  # for next bouncing check
    
    
        if (Switch_A and Switch_B):  # Both one active? Yes -> end of sequence
            self.rotaryLock.acquire()  # get lock 
            if A_or_B == self.encoderB:  # Turning direction depends on 
                self.rotaryCounter += 1  # which input gave last interrupt
            else:  # so depending on direction either
                self.rotaryCounter -= 1  # increase or decrease counter
            self.rotaryLock.release()  # and release lock

    def processRotary(self):
        self.rotaryLock.acquire()  # get lock for rotary switch
        self.newCounter = self.rotaryCounter  # get counter value
        self.rotaryCounter = 0  # RESET IT TO 0
        self.rotaryLock.release()  # and release lock
                
        if self.newCounter != 0:  # Counter has CHANGED
            volumeDelta = self.newCounter * abs(self.newCounter)  # Decrease or increase volume 
            self.volume += volumeDelta
            
            self.logger.debug("Volume change: {:d} (current volume: {:d})".format(volumeDelta, self.volume))
            print("Volume change: {:d}; newCounter: {:d}; volume = {:d}".format(volumeDelta, self.newCounter, self.volume))  # some test print
            if self.queue is not None:
                try:
                    self.queue.put("VOLUME {:d}".format(volumeDelta))
                except:
                    pass
                
            if self.reset is not None:
                self.reset.set()
            self.incrementNbOperations()
                        
    def incrementNbOperations(self):
        self.nbOperations += 1
        # Make sure the value does not grow too big
        if self.nbOperations > 100000:
            self.nbOperations = 0
        
    # Increment active bank (cycle through leds)
    # Cycle backwards with reverseOrder = True
    # Only restore the currently active bank when restore = True (no increment)
    def incrementBank(self, reverseOrder=False, restore=False):    
        increment = 1 if not reverseOrder else -1
            
        if not restore:
            self.ledStates.rotate(increment)
            
        for l in self.ledPorts:
            GPIO.output(l, self.ledStates[self.ledPorts.index(l)])
                
        if self.ledStates.count(GPIO.HIGH) != 1:
            self.initLeds()
            
    def switchAllLeds(self, state):
        if state:
            state = GPIO.HIGH
        else:
            state = GPIO.LOW
            
        for l in self.ledPorts:
            GPIO.output(l, state)       
    
    def getBank(self):
        # Return the currently active bank (A, B, C, ...)
        try:
            return chr(65 + list(self.ledStates).index(GPIO.HIGH))
        except:
            self.initLeds()
        
        # Default: Bank A
        return 'A'
    
    def getSwitch(self, channel):
        # Return the number corresponding to the given channel (e.g. 'Switch 4' -> 4)
        return self.switchNbs[channel]
            
    # Mode switch
    def toggleAltMode(self):
        if not self.altMode and GPIO.input(self.modePort) == GPIO.LOW:
            self.logger.debug("Activating alt-mode")
            self.activateAltMode()
        else:
            self.logger.debug("Deactivating alt-mode")
            self.deactivateAltMode()
    def activateAltMode(self):
        self.altMode = True
        # Take note of the currently selected room
        self.currentRoomNb = self.getActiveRoomNb()
        self.logger.debug("Activating alt-mode: Current room number is {:d}".format(self.currentRoomNb))
        self.activateAltModeCurrentNbOperations = self.nbOperations
        
    def deactivateAltMode(self):
        self.altMode = False

        # Make sure the number of operations has not changed since activating alt=mode
        # (in order to detect cases where releasing the mode switch has not been properly registered)
        if self.nbOperations != self.activateAltModeCurrentNbOperations + 1 \
        and self.nbOperations != 1: # Case where self.nbOperations has been reset
            self.logger.debug("Discarding room change: Other keys pressed since activating alt-mode)")
            return
            
        # Check whether the active room has been changed:
        curRoomNb = self.getActiveRoomNb()
        if curRoomNb != self.currentRoomNb:
            self.logger.debug("The current room number has been changed to {:d} (used to be {:d})".format(curRoomNb, self.currentRoomNb))
            self.queue.put("ROOM {:d}".format(curRoomNb))
            
    def isAltModeOn(self):
        if self.altMode and GPIO.input(self.modePort) == GPIO.LOW:
            return True 
        else:
            self.deactivateAltMode()
            return False
        
    # Check that alt-mode is still active (to prevent quick releases of the mode switch 
    # to go undetected) 
    def checkAltMode(self):
        if self.altMode and GPIO.input(self.modePort) != GPIO.LOW:
            self.deactivateAltMode()
        
    def activateShiftMode(self):
        self.shiftMode = True
        self.altMode = False
    def deactivateShiftMode(self):
        self.shiftMode = False
    def isShiftModeOn(self):
            return self.shiftMode

        
    # Callback for switches (start playlist)
    def callbackSwitch(self, channel):
        self.logger.debug("Switch {} pressed (channel {:d}, alt. mode: {}, shift mode: {})".format(self.switches[channel], 
                                                                               channel, 
                                                                               "ON" if self.isAltModeOn() else "OFF",
                                                                               "ON" if self.isShiftModeOn() else "OFF"))
        print("Edge detected on channel {:d} [Switch ID: {}, alt. mode: {}, shift mode: {}]".format(channel, 
                                                                                    self.switches[channel], 
                                                                                    "ON" if self.isAltModeOn() else "OFF",
                                                                                    "ON" if self.isShiftModeOn() else "OFF"))

        if self.queue is not None:
            try:
                if self.isAltModeOn():
                    self.queue.put("TRACK {:d}".format(self.getSwitch(channel)))
                elif self.isShiftModeOn():
                    self.queue.put("ROOM {:d}".format(self.getSwitch(channel)))
                else:
                    self.queue.put("PLAYLIST {} {:d}".format(self.getBank(), self.getSwitch(channel)))
            except:
                pass

        if self.isShiftModeOn():
            self.deactivateShiftMode()
            
        if self.reset is not None:
            self.reset.set()
        self.incrementNbOperations()
        
    # Callback for bank switch 
    def callbackBankSwitch(self, channel):
        self.logger.debug("Bank switch pressed (channel {:d}, alt. mode: {}, shift mode: {})".format(channel, 
                                                                               "ON" if self.isAltModeOn() else "OFF",
                                                                               "ON" if self.isShiftModeOn() else "OFF"))
        print("Edge detected on channel {:d} [Bank switch, alt. mode: {}, shift mode: {}]".format(channel, 
                                                                                    "ON" if self.isAltModeOn() else "OFF",
                                                                                    "ON" if self.isShiftModeOn() else "OFF"))
        if not self.isShiftModeOn():
            self.incrementBank(self.isAltModeOn())
        else:
            self.deactivateShiftMode()
        
        if self.reset is not None:
            self.reset.set()
        self.incrementNbOperations()
        
    # Callback for mode switch
    def callbackModeSwitch(self, channel):
        self.logger.debug("Mode switch pressed (channel {:d})".format(channel))
        print("Edge detected on channel {:d} [Mode switch]".format(channel))
        
        self.toggleAltMode()
        
        if self.reset is not None:
            self.reset.set()
        self.incrementNbOperations()
        
     # Callback for switches (play/pause, skip forward/backward)
    def callbackControlSwitch(self, channel):
        self.logger.debug("Switch {} pressed (channel {:d}, alt. mode: {}, shift mode: {})".format(self.switches[channel], 
                                                                               channel, 
                                                                               "ON" if self.isAltModeOn() else "OFF",
                                                                               "ON" if self.isShiftModeOn() else "OFF"))
        print("Edge detected on channel {:d} [Switch ID: {}, alt. mode: {}, shift mode: {}]".format(channel, 
                                                                                    self.switches[channel], 
                                                                                    "ON" if self.isAltModeOn() else "OFF",
                                                                                    "ON" if self.isShiftModeOn() else "OFF"))

        if self.switches[channel] == self.playSwitch and self.isShiftModeOn():
            if self.switches[channel] == self.playSwitch:
                self.deactivateShiftMode()
        else:
            if self.queue is not None:
                try:
                    if self.switches[channel] == self.playSwitch and not self.isAltModeOn():
                        self.queue.put("PLAY/PAUSE")
                    elif self.switches[channel] == self.forwardSwitch:
                        self.queue.put("FORWARD")
                    elif self.switches[channel] == self.backSwitch and not self.isAltModeOn():
                        self.queue.put("BACK")
                except:
                    pass

        if self.switches[channel] == self.backSwitch and self.isAltModeOn():
            # Key combination: If Mode + Back are pressed together for a certain time, switch off the pi  
            self.initiateSwitchOff()

        if self.switches[channel] == self.playSwitch and self.isAltModeOn():
            # Key combination: If Mode + Play are pressed together, switch to shift mode (select room with playlist buttons) 
            self.activateShiftMode()
            
        if self.reset is not None:
            self.reset.set()
        self.incrementNbOperations()

    # Start procedure to switch off the pi under certain conditions
    def initiateSwitchOff(self):
        self.logger.debug("Initiating switch off (Key combination Mode + Back)") 
        # Take into account a second call before the first switch off procedure has completed
        try:
            if self.switchOffTimer.is_alive():
                self.switchOffTimer.cancel()
        except:
            pass
        
        try:
            # Timer to trigger switch off after a given time in case the key combination is continuously pressed
            self.switchOffTimePeriod = 3 # s
            self.switchOffTimer = threading.Timer(self.switchOffTimePeriod, self.completeSwitchOff)
            self.switchOffTimer.setName("SwitchOffTimer")
            self.switchOffTimer.start()
            self.switchOffCurrentNbOperations = self.nbOperations
        except:
            self.logger.error("Problem initiating switch off")
        
    # If the conditions are fulfilled, switch off the pi
    def completeSwitchOff(self):
        self.logger.debug("Attempting to complete switch off (Key combination Mode + Back)") 

        # Make sure the number of operations has not changed since initiating the switch off procedure
        if self.nbOperations != self.switchOffCurrentNbOperations + 1 \
        and self.nbOperations != 1: # Case where self.nbOperations has been reset
            self.logger.debug("Canceling switch off (Key combination Mode + Back): Other keys have been pressed in the meantime") 
            return
        
        # Make sure the key combination is still being pressed
        if GPIO.input(self.modePort) != GPIO.LOW or GPIO.input(self.backPort) != GPIO.LOW:
            self.logger.debug("Canceling switch off (Key combination Mode + Back): Key combination no longer pressed") 
            return
        
        # All the conditions are fulfilled: Send switch off signal
        self.logger.debug("Mode and Back pressed for {} seconds: Sending signal to shut down the pi".format(self.switchOffTimePeriod))

        if self.queue is not None:
            try:
                self.queue.put("SHUTDOWN")
            except:
                pass
        
    # When shift mode is on, signal it by blinking all bank leds until a room is selected or play is pressed anew    
    def blinkLedsForShift(self):
        # Not in shift mode: Nothing to do
        if not self.blinking and not self.isShiftModeOn():
            return
        
        # Start blinking
        if not self.blinking and self.isShiftModeOn():
            self.blinking = True
            # Switch on all leds
            self.switchAllLeds(True)
            self.blinkRefTime = time.time()
            self.blinkState = True
            return
            
        # Stop blinking
        if self.blinking and not self.isShiftModeOn():
            self.blinking = False
            # Switch on only the led corresponding to the current bank 
            self.incrementBank(False, True)
            return
            
        # Continue blinking
        if self.blinking and self.isShiftModeOn():
            # Alternately switch on and off all leds
            if time.time() - self.blinkRefTime >= self.blinkPeriod:
                self.blinkRefTime = time.time()
                self.blinkState = not self.blinkState
                self.switchAllLeds(self.blinkState)
        
            
                    
    def run(self, stopper=None, queue=None, reset=None):
        try:
            self.logger.info("Starting main loop")  
            self.stopper = stopper
            print("Reacting to interrupts from switches")
            self.queue = queue

            self.reset = reset
              
            while True:
                sleep(0.1)  # sleep 100 msec       
                                                    # because of threading make sure no thread
                                                    # changes value until we get them
                                                    # and reset them
                                                    
                self.processRotary()
                
                self.checkAltMode()

                if self.stopRequested:
                    self.logger.debug("Requesting stop")
                    break

                if self.stopper is not None:
                    try:
                        if self.stopper.is_set():
                            break
                    except:
                        pass
                    
                self.blinkLedsForShift()
 
        except KeyboardInterrupt:
            self.logger.info("Stop (Ctrl-C from main loop)") 
            print("Stop (Ctrl-C)")
        finally:
            # clean up GPIO on exit  
            self.logger.debug("Cleaning up GPIO")
            GPIO.cleanup()
#            self.logger.debug("Canceling shutdown timer")
#            try:
#                self.shutdownTimer.join()
#            except:
#                pass
#            self.logger.debug("Canceling switch off timer")
#            try:
#                self.switchOffTimer.join()
#            except:
#                pass

            self.logger.debug("Canceling switch off timer")
            try:
                self.switchOffTimer.cancel()
            except:
                pass
            self.logger.debug("Over.")
            
        self.logger.debug("Bye!")

    def requestStop(self):
        self.stopRequested = True

if __name__ == '__main__':
    # Logging
#    logging.basicConfig(filename='userInterface.log', 
#                        level=logging.DEBUG, 
#                        format='%(asctime)s %(levelname)s:%(message)s', 
#                        datefmt='%Y-%m-%d %H:%M:%S')
    logFormatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(pathname)s:%(lineno)d) %(message)s')
    logFile = 'userInterface.log'
    logHandler = RotatingFileHandler(logFile, mode='a', maxBytes=5*1024*1024, 
                                     backupCount=2, encoding=None, delay=0)
    logHandler.setFormatter(logFormatter)
    logHandler.setLevel(logging.DEBUG)
    logger = logging.getLogger('root')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logHandler)    

    logger.info("Creating instance of UserInterface") 
    ui = UserInterface(logger)
    try:
        ui.run()
    except KeyboardInterrupt:
        logger.info("Stop (Ctrl-C from __main__)") 
        print("Stop (Ctrl-C) [from main]")
        ui.requestStop()
