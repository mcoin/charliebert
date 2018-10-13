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
import re
    
    
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
        self.u2pQueue = None
        self.p2uQueue = None
        
        # Number of operations (key presses): Incremented after each key press
        self.nbOperations = 0
        # Control counters
        self.switchOffCurrentNbOperations = 0
        self.activateAltModeCurrentNbOperations = 0
                
        # Indicator for shift mode: if true, blink all bank leds
        self.blinking = False
        # Indicator for alt/playlist mode: if true, blink the current bank led
        self.blinkingOne = False
        # Period for blinking leds (in seconds)
        self.blinkPeriod = 0.5
        
        # Progress indicator: Cycle through all speaker leds while completing a task
        self.cyclingSpeakerLeds = False
        self.progress = False
        
        # SMBUS stuff for additional ports via MCP23017 chip
        self.initMcp()
        self.currentRoomNb = None
        self.currentNetworkNb = None
        self.codeForCyclingSpeakerLeds = None

        # Parser for the p2u queue
        self.parser = re.compile("^([A-Z/]+)(\s+([A-Z]+))*(\s+([-0-9]+))*(\s*;\s+([-0-9]+))*\s*$")

        
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
        # First 6 bits
        self.roomNbMap = {
                        0x3B: 1, 0x37: 2, 0x2F: 3, 0x1F: 4, 0x3E: 5, 0x3D: 6
                        }
        # Last 2 bits
        self.networkNbMap = {
                        0xC0: 1, 0x80: 2, 0x40: 3
                        }
        
        # Define device
        self.mcpBus = smbus.SMBus(1)
        # Set pullup resistors
        self.mcpBus.write_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap['GPPUA'], 0xFF)
        self.mcpBus.write_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap['GPPUB'], 0xFF)
        # Set direction (input) 
        self.mcpBus.write_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap['IODIRA'], 0x00)
        self.mcpBus.write_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap['IODIRB'], 0xFF)

        self.mcpBus.write_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap['GPIOA'], 0x00)
    
    def endMcp(self):
        # Switch leds off
        self.mcpBus.write_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap['GPIOA'], 0x00)

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
        
    def writeMcp(self, reg, sw):
        #self.logger.debug("writeMcp for reg = {}, sw = {}".format(reg, sw))
        if reg in self.mcpRegisterMap:
            try:
                #self.logger.debug("writeMcp: reg = {} exists".format(reg))
                return self.mcpBus.write_byte_data(self.mcpDeviceAddress, self.mcpRegisterMap[reg], sw)
            except:
                #self.logger.debug("writeMcp: Cannot write data for reg = {}".format(reg))
                raise
        else:
            #self.logger.debug("writeMcp: reg = {} does not exist".format(reg))
            raise
        
    def getActiveRoomNb(self):
        #self.logger.debug("getActiveRoomNb")
        try:
            sw = self.readMcp('GPIOB')
            # Apply mask (extract first 6 bits)
            sw = sw & 0x3F
            #self.logger.debug("sw = {}".format(sw))
            #self.logger.debug("room = {}".format(self.roomNbMap[sw]))
            return self.roomNbMap[sw]
        except:
            self.logger.error("Error while determining the room number")
            return 0
        
    def getActiveNetworkNb(self):
        #self.logger.debug("getActiveNetworkNb")
        try:
            sw = self.readMcp('GPIOB')
            # Apply mask (extract last 2 bits)
            sw = sw & 0xC0
            #self.logger.debug("sw = {}".format(sw))
            #self.logger.debug("room = {}".format(self.networkNbMap[sw]))
            return self.networkNbMap[sw]
        except:
            self.logger.error("Error while determining the room number")
            return 0
        
    def setActiveSpeakerLeds(self, network, room):
        #self.logger.debug("setActiveSpeakerLeds")
        try:
            if network == 2:
                # Home
                if room == 1:
                    sw = 0x80
                elif room == 2:
                    sw = 0x10
                elif room == 3:
                    sw = 0x04
                elif room == 4:
                    sw = 0x08
                elif room == 5:
                    sw = 0x20
                elif room == 6:
                    sw = 0x40
            elif network == 3:
                # Charliebert
                sw = 0x02
            else:
                # Oben
                if room % 2 == 0:
                    sw = 0x1C
                else:
                    sw = 0xE0
            #self.logger.debug("sw = {}".format(sw))
            self.writeMcp('GPIOA', sw)
        except:
            self.logger.error("Error setting the room & network leds")

    def cycleSpeakerLeds(self):
        #self.logger.debug("cycleSpeakerLeds")
        try:
            if self.codeForCyclingSpeakerLeds == 0x40:
                self.codeForCyclingSpeakerLeds = 0x80
            elif self.codeForCyclingSpeakerLeds == 0x80:
                self.codeForCyclingSpeakerLeds = 0x10
            elif self.codeForCyclingSpeakerLeds == 0x10:
                self.codeForCyclingSpeakerLeds = 0x04
            elif self.codeForCyclingSpeakerLeds == 0x04:
                self.codeForCyclingSpeakerLeds = 0x08
            elif self.codeForCyclingSpeakerLeds == 0x08:
                self.codeForCyclingSpeakerLeds = 0x20
            elif self.codeForCyclingSpeakerLeds == 0x20:
                self.codeForCyclingSpeakerLeds = 0x40
            else:
                self.codeForCyclingSpeakerLeds = 0x40
                
            #self.logger.debug("self.codeForCyclingSpeakerLeds = {}".format(self.codeForCyclingSpeakerLeds))
            self.writeMcp('GPIOA', self.codeForCyclingSpeakerLeds)
        except:
            self.logger.error("Error cycling the room leds")
        
    
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
                    9: "Forward",
                    11:  "Back",
                    27: "Bank",
                    17: "Mode"
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
        # Indicate whether alternate mode 3 (alt-playlist) is on (upon holding down the Mode & Foraward buttons)
        self.altPlaylistMode = False        
        
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
                GPIO.add_event_detect(port, GPIO.FALLING, callback=self.callbackBankSwitch, bouncetime=1000)
            elif name == self.modeSwitch:
                GPIO.add_event_detect(port, GPIO.BOTH, callback=self.callbackModeSwitch, bouncetime=1000)
            elif port in self.switchNbs:
                GPIO.add_event_detect(port, GPIO.FALLING, callback=self.callbackSwitch, bouncetime=1000)  
            else:
                GPIO.add_event_detect(port, GPIO.FALLING, callback=self.callbackControlSwitch, bouncetime=1000)
                
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
            if self.u2pQueue is not None:
                try:
                    self.u2pQueue.put("VOLUME {:d}".format(volumeDelta))
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
        # Take note of the currently selected room & network
        self.currentRoomNb = self.getActiveRoomNb()
        self.currentNetworkNb = self.getActiveNetworkNb()
        self.logger.debug("Activating alt-mode: Current room number is {:d}, network number is {:d}".format(self.currentRoomNb, self.currentNetworkNb))
        self.activateAltModeCurrentNbOperations = self.nbOperations
        
    def deactivateAltMode(self):
        self.logger.debug("Deactivating alt-mode")
        self.altMode = False

        # Make sure the number of operations has not changed since activating alt=mode
        # (in order to detect cases where releasing the mode switch has not been properly registered)
        if self.nbOperations != self.activateAltModeCurrentNbOperations + 1 \
        and self.nbOperations != 1: # Case where self.nbOperations has been reset
            self.logger.debug("Discarding room change: Other keys pressed since activating alt-mode)")
            return
            
        changes = False

        # Check whether the active room has been changed:
        self.logger.debug("Checking whether the active room has changed")
        curRoomNb = self.getActiveRoomNb()
        self.logger.debug("curRoomNb = {:d}".format(curRoomNb))
        self.logger.debug("self.currentRoomNb = {}".format(self.currentRoomNb))
        if self.currentRoomNb is not None and curRoomNb != self.currentRoomNb:
            self.logger.debug("The current room number has been changed to {:d} (used to be {:d})".format(curRoomNb, self.currentRoomNb))
            if curRoomNb == 0 or self.currentRoomNb == 0:
                self.logger.error("Wrong room number, skipping command (curRoomNb = {}, self.currentRoomNb = {})".format(curRoomNb, self.currentRoomNb))
            else:
                changes = True
                self.logger.debug("Actually changing the currently active room")
                self.u2pQueue.put("ROOM {:d}".format(curRoomNb))
            
        # Check whether the active network has been changed:
        self.logger.debug("Checking whether the active network has changed")
        curNetworkNb = self.getActiveNetworkNb()
        self.logger.debug("curNetworkNb = {}".format(curNetworkNb))
        if self.currentNetworkNb is not None and curNetworkNb != self.currentNetworkNb:
            self.logger.debug("The current network number has been changed to {:d} (used to be {:d})".format(curNetworkNb, self.currentNetworkNb))
            if curNetworkNb == 0 or self.currentNetworkNb == 0:
                self.logger.error("Wrong network number, skipping command (curNetworkNb = {}, self.currentNetworkNb = {})".format(curNetworkNb, self.currentNetworkNb))
            else:
                changes = True
                self.logger.debug("Actually changing the currently active network")
                self.u2pQueue.put("NET {:d}".format(curNetworkNb))

        if changes:
            self.logger.debug("Changing the currently active speaker led indicator")
            self.setActiveSpeakerLeds(curNetworkNb, curRoomNb)

            
    def isAltModeOn(self):
        self.logger.debug("Determining whether Alt-Mode is on")
        if self.altMode and GPIO.input(self.modePort) == GPIO.LOW:
            self.logger.debug("Alt-Mode is on")
            return True 
        else:
            self.logger.debug("Alt-Mode is off")
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

    def activateAltPlaylistMode(self):
        self.altPlaylistMode = True
        self.altMode = False
    def deactivateAltPlaylistMode(self):
        self.altPlaylistMode = False
    def isAltPlaylistModeOn(self):
        return self.altPlaylistMode

        
    # Callback for switches (start playlist)
    def callbackSwitch(self, channel):
        self.logger.debug("Switch {} pressed (channel {:d}, alt. mode: {}, shift mode: {}, alt-playlist mode: {})".format(self.switches[channel], 
                                                                               channel, 
                                                                               "ON" if self.isAltModeOn() else "OFF",
                                                                               "ON" if self.isShiftModeOn() else "OFF",
                                                                               "ON" if self.isAltPlaylistModeOn() else "OFF"))
        print("Edge detected on channel {:d} [Switch ID: {}, alt. mode: {}, shift mode: {}, alt-playlist mode: {}]".format(channel, 
                                                                                    self.switches[channel], 
                                                                                    "ON" if self.isAltModeOn() else "OFF",
                                                                                    "ON" if self.isShiftModeOn() else "OFF",
                                                                                    "ON" if self.isAltPlaylistModeOn() else "OFF"))

        if self.u2pQueue is not None:
            try:
                if self.isAltModeOn():
                    self.u2pQueue.put("TRACK {:d}".format(self.getSwitch(channel)))
                elif self.isShiftModeOn():
                    self.u2pQueue.put("COMMAND {:d}".format(self.getSwitch(channel)))
                elif self.isAltPlaylistModeOn():
                    self.u2pQueue.put("ALTPLAYLIST {} {:d}".format(self.getBank(), self.getSwitch(channel)))
                else:
                    self.u2pQueue.put("PLAYLIST {} {:d}".format(self.getBank(), self.getSwitch(channel)))
            except:
                pass

        if self.isShiftModeOn():
            self.deactivateShiftMode()
            
        if self.isAltPlaylistModeOn():
            self.deactivateAltPlaylistMode()
            
        if self.reset is not None:
            self.reset.set()
        self.incrementNbOperations()
        
    # Callback for bank switch 
    def callbackBankSwitch(self, channel):
        self.logger.debug("Bank switch pressed (channel {:d}, alt. mode: {}, shift mode: {}, alt-playlist mode: {})".format(channel, 
                                                                               "ON" if self.isAltModeOn() else "OFF",
                                                                               "ON" if self.isShiftModeOn() else "OFF",
                                                                               "ON" if self.isAltPlaylistModeOn() else "OFF"))
        print("Edge detected on channel {:d} [Bank switch, alt. mode: {}, shift mode: {}, alt-playlist mode: {}]".format(channel, 
                                                                                    "ON" if self.isAltModeOn() else "OFF",
                                                                                    "ON" if self.isShiftModeOn() else "OFF",
                                                                                    "ON" if self.isAltPlaylistModeOn() else "OFF"))
        self.logger.debug("Increment bank or deactivate shift mode")
        if not self.isShiftModeOn():
            self.logger.debug("Increment bank")
            self.incrementBank(self.isAltModeOn())
        else:
            self.logger.debug("Deactivate shift mode")
            self.deactivateShiftMode()
        
        self.logger.debug("Reset timer if applicable")
        if self.reset is not None:
            self.logger.debug("Reset timer")
            self.reset.set()

        self.logger.debug("Increment nb ops.")
        self.incrementNbOperations()

        self.logger.debug("Over")
        
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
        self.logger.debug("Switch {} pressed (channel {:d}, alt. mode: {}, shift mode: {}, alt-playlist mode: {})".format(self.switches[channel], 
                                                                               channel, 
                                                                               "ON" if self.isAltModeOn() else "OFF",
                                                                               "ON" if self.isShiftModeOn() else "OFF",
                                                                               "ON" if self.isAltPlaylistModeOn() else "OFF"))
        print("Edge detected on channel {:d} [Switch ID: {}, alt. mode: {}, shift mode: {}, alt-playlist mode: {}]".format(channel, 
                                                                                    self.switches[channel], 
                                                                                    "ON" if self.isAltModeOn() else "OFF",
                                                                                    "ON" if self.isShiftModeOn() else "OFF",
                                                                                    "ON" if self.isAltPlaylistModeOn() else "OFF"))

        if self.switches[channel] == self.playSwitch and self.isShiftModeOn():
            self.deactivateShiftMode()
        elif self.switches[channel] == self.forwardSwitch and self.isAltPlaylistModeOn():
            self.deactivateAltPlaylistMode()
        else:
            if self.u2pQueue is not None:
                try:
                    if self.switches[channel] == self.playSwitch and not self.isAltModeOn():
                        self.u2pQueue.put("PLAY/PAUSE")
                    elif self.switches[channel] == self.forwardSwitch and not self.isAltModeOn():
                        self.u2pQueue.put("FORWARD")
                    elif self.switches[channel] == self.backSwitch and not self.isAltModeOn():
                        self.u2pQueue.put("BACK")
                except:
                    pass

        if self.switches[channel] == self.playSwitch and self.isAltModeOn():
            # Key combination: If Mode + Play are pressed together, switch to shift mode (select room with playlist buttons) 
            self.activateShiftMode()
            self.deactivateAltPlaylistMode()
            
        if self.switches[channel] == self.forwardSwitch and self.isAltModeOn():
            # Key combination: If Mode + Forward are pressed together, switch to alt-playlist mode (start an alternative playlist) 
            self.activateAltPlaylistMode()
            self.deactivateShiftMode()

        if self.switches[channel] == self.backSwitch and self.isAltModeOn():
            # Key combination: If Mode + Back are pressed together for a certain time, switch off the pi  
            self.initiateSwitchOff()
            
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

        if self.u2pQueue is not None:
            try:
                self.u2pQueue.put("SHUTDOWN")
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
                
    # When alt-playlist mode is on, signal it by blinking the current bank led until a playlist is selected or forward is pressed anew    
    def blinkLedsForAltPlaylist(self):
        # Not in alt-playlist mode: Nothing to do
        if not self.blinkingOne and not self.isAltPlaylistModeOn():
            return
        
        # Start blinking
        if not self.blinkingOne and self.isAltPlaylistModeOn():
            self.blinkingOne = True
            # Switch off all leds
            self.switchAllLeds(False)
            self.blinkRefTime = time.time()
            self.blinkState = True
            return
            
        # Stop blinking
        if self.blinkingOne and not self.isAltPlaylistModeOn():
            self.blinkingOne = False
            # Switch on only the led corresponding to the current bank 
            self.incrementBank(False, True)
            return
            
        # Continue blinking
        if self.blinkingOne and self.isAltPlaylistModeOn():
            # Alternately switch on and off all leds
            if time.time() - self.blinkRefTime >= self.blinkPeriod:
                self.blinkRefTime = time.time()
                self.blinkState = not self.blinkState
                if self.blinkState:
                    # Switch off all leds
                    self.switchAllLeds(False)
                else:
                    # Switch on only the led corresponding to the current bank 
                    self.incrementBank(False, True)                                      
        
    # When performing an action (e.g. syncing playlists), signal it by cycling all speaker leds until completion    
    def cycleSpeakerLedsForProgress(self):
        #self.logger.debug("cycleSpeakerLedsForProgress (cyclingSpeakerLeds: {}, progress: {})".format(self.cyclingSpeakerLeds, self.progress))
        # Not in progress mode: Nothing to do
        if not self.cyclingSpeakerLeds and not self.progress:
            #self.logger.debug("cycleSpeakerLedsForProgress: Not active")
            return
        
        # Start cycling
        if not self.cyclingSpeakerLeds and self.progress:
            self.logger.debug("Cycling starting (current network {} and room {})".format(self.curNetworkNb, self.curRoomNb))
            self.cyclingSpeakerLeds = True
            self.blinkRefTime = time.time()
            self.cycleSpeakerLeds()
            
        # Stop cycling
        if self.cyclingSpeakerLeds and not self.progress:
            self.cyclingSpeakerLeds = False
            # Switch on only the led corresponding to the current room/network 
            self.logger.debug("Cycling over: Switching on leds for network {} and room {}".format(self.curNetworkNb, self.curRoomNb))
            #self.setActiveSpeakerLeds(self.curNetworkNb, self.curRoomNb)
            #return
            
        # Continue cycling
        if self.cyclingSpeakerLeds and self.progress:
            # Cycle through all speaker leds
            #self.logger.debug("cycleSpeakerLedsForProgress: Loop")
            if time.time() - self.blinkRefTime >= self.blinkPeriod:
                self.logger.debug("cycleSpeakerLedsForProgress: Switch on next led")
                self.blinkRefTime = time.time()
                self.cycleSpeakerLeds()
                
    def processCommands(self):
        if not self.p2uQueue.empty():
            command = self.p2uQueue.get(False)

            # Process commands using the following mini-parser
            m = self.parser.match(command)
            try:
                if m.group(1) == "NETWORK/ROOM":
                    networkIndex = int(m.group(5))
                    roomIndex = int(m.group(7))
                    self.logger.debug("Command NETWORK ({:d}) / ROOM ({:d})".format(networkIndex, roomIndex))
                    self.setActiveSpeakerLeds(networkIndex, roomIndex)
                elif m.group(1) == "PROGRESS":
                    if (m.group(3) == "START"):
                        self.logger.debug("Command PROGRESS START")
                        self.progress = True
                        self.logger.debug("self.progress: {}".format(self.progress))
                    elif (m.group(3) == "STOP"):
                        self.logger.debug("Command PROGRESS STOP")
                        self.progress = False
                        self.logger.debug("self.progress: {}".format(self.progress))
                else:
                   raise 
            except:
                self.logger.error("Unrecognized command: '{}'".format(command))


                    
    def run(self, stopper=None, u2pQueue=None, p2uQueue=None, reset=None):
        try:
            self.logger.info("Starting main loop")  
            self.stopper = stopper
            print("Reacting to interrupts from switches")
            self.u2pQueue = u2pQueue
            self.p2uQueue = p2uQueue

            self.reset = reset
              
            while True:
                sleep(0.1)  # sleep 100 msec       
                                                    # because of threading make sure no thread
                                                    # changes value until we get them
                                                    # and reset them
                                                    
                self.processRotary()
                
                self.checkAltMode()

                self.processCommands()
                    
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
                self.blinkLedsForAltPlaylist()
                self.cycleSpeakerLedsForProgress()
 
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

            # Clean up MCP state
            self.logger.debug("Cleaning up MCP")
            self.endMcp()

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
