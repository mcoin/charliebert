#!/usr/bin/env python3.4
import RPi.GPIO as GPIO 
from collections import deque
import threading
from time import sleep
import logging
from distutils.cmd import Command
    
    
class UserInterface:
    
    def __init__(self):
        logging.info("Initializing instance of UserInterface")
        
        # GPIO settings
        GPIO.setwarnings(True)
        GPIO.setmode(GPIO.BCM)
        
        # Switches
        logging.debug("Setting up switches")
        self.initSwitches()
        
        # LEDs
        logging.debug("Setting up LEDs")
        self.initLeds()
    
        # Rotary encoder
        logging.debug("Setting up rotary encoder")
        self.initRotaryEncoder()
    
        # Break the main loop if marked True
        self.stopRequested = False
        
        # Event queue to trigger actions from the server
        self.queue = None
        
        # Timer to trigger a shutdown after a given period of inactivity
        self.shutdownTimePeriod = 1800 # s
        self.shutdownTimer = threading.Timer(self.shutdownTimePeriod, self.sendShutdownSignal)
        self.shutdownTimer.setName("ShutdownTimer")
        
        # Number of operations (key presses): Incremented after each key press
        self.nbOperations = 0
        
        # Indicator for shift mode: if true, blink all bank leds
        self.blinking = False
        # Period for blinking leds (in seconds)
        self.blinkPeriod = 0.5
        
    
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
        self.shifttMode = False
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
                GPIO.add_event_detect(port, GPIO.FALLING, callback=self.callbackBankSwitch, bouncetime=300)
            elif name == self.modeSwitch:
                GPIO.add_event_detect(port, GPIO.FALLING, callback=self.callbackModeSwitch, bouncetime=300)
            elif port in self.switchNbs:
                GPIO.add_event_detect(port, GPIO.FALLING, callback=self.callbackSwitch, bouncetime=300)  
            else:
                GPIO.add_event_detect(port, GPIO.FALLING, callback=self.callbackControlSwitch, bouncetime=300)
                
    def initLeds(self):
        # LEDs for the different playlist banks: Ports and names
        self.ledPorts = [6, 19, 13, 26]
        self.ledNames = ["Bank A", "Bank B", "Bank C", "Bank D"]
        # State of the bank leds
        self.ledStates = deque()
        # Checks (the lists have to have the same number of elements)
        assert(len(self.ledPorts) == len(self.ledNames))
        assert(len(ledStates) == len(self.ledNames))
        # LEDs: {Port, Name}
        leds = dict(zip(self.ledPorts, self.ledNames))
        # Name of the LED which is ON by default at startup
        defaultLed = "Bank A"
        assert(defaultLed in self.ledNames)
        self.activeLed = self.ledPorts[self.ledNames.index(defaultLed)]
        self.activeLedName = leds[activeLed]
        # Set the corresponding ports as output with state HIGH for the 1st one
        for l, name in leds.items():
            GPIO.setup(l, GPIO.OUT)
            GPIO.output(l, GPIO.HIGH if name == defaultLed else GPIO.LOW)
            self.ledStates.append(GPIO.HIGH if name == defaultLed else GPIO.LOW)


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
            
            logging.debug("Volume change: {:d} (current volume: {:d})".format(volumeDelta, self.volume))
            print("Volume change: {:d}; newCounter: {:d}; volume = {:d}".format(volumeDelta, self.newCounter, self.volume))  # some test print
            if self.queue is not None:
                try:
                    self.queue.put("VOLUME {:d}".format(volumeDelta))
                except:
                    pass
                
            self.resetShutdownTimer()
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
    def activateAltMode(self):
        self.altMode = True
    def isAltModeOn(self):
        if self.altMode and GPIO.input(self.modePort) == GPIO.LOW:
            return True 
        else:
            self.altMode = False
            return False
    def activateShiftMode(self):
        self.shiftMode = True
        self.altMode = False
    def deactivateShiftMode(self):
        self.shiftMode = False
    def isShiftModeOn(self):
            return self.shiftMode
                    
    # Function that sends a shutdown command after a period of inactivity
    def sendShutdownSignal(self):
        logging.debug("No activity for {} seconds: Sending signal to shut down the pi".format(self.shutdownTimePeriod))

        if self.queue is not None:
            try:
                self.queue.put("SHUTDOWN")
            except:
                pass
            
    # Reset the shutdown timer with each new key press
    def resetShutdownTimer(self):
        try:
            # Cancel current timer
            self.shutdownTimer.cancel()
            # Restart timer to monitor inactivity after the last key press
            self.shutdownTimer = threading.Timer(self.shutdownTimePeriod, self.sendShutdownSignal)
            self.shutdownTimer.setName("ShutdownTimer")
            self.shutdownTimer.start()
        except:
            logging.error("Problem encountered when trying to reset the shutdown timer")

        
    # Callback for switches (start playlist)
    def callbackSwitch(self, channel):
        logging.debug("Switch {} pressed (channel {:d}, alt. mode: {}, shift mode: {})".format(self.switches[channel], 
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
                    self.deactivateShiftMode()
                else:
                    self.queue.put("PLAYLIST {} {:d}".format(self.getBank(), self.getSwitch(channel)))
            except:
                pass
            
        self.resetShutdownTimer()
        self.incrementNbOperations()
        
    # Callback for bank switch 
    def callbackBankSwitch(self, channel):
        logging.debug("Bank switch pressed (channel {:d}, alt. mode: {}, shift mode: {})".format(channel, 
                                                                               "ON" if self.isAltModeOn() else "OFF",
                                                                               "ON" if self.isShiftModeOn() else "OFF"))
        print("Edge detected on channel {:d} [Bank switch, alt. mode: {}, shift mode: {}]".format(channel, 
                                                                                    "ON" if self.isAltModeOn() else "OFF",
                                                                                    "ON" if self.isShiftModeOn() else "OFF"))
        if not self.isShiftModeOn():
            self.incrementBank(self.isAltModeOn())
        
        self.resetShutdownTimer()
        self.incrementNbOperations()
        
    # Callback for mode switch
    def callbackModeSwitch(self, channel):
        logging.debug("Mode switch pressed (channel {:d})".format(channel))
        print("Edge detected on channel {:d} [Mode switch]".format(channel))
        
        self.activateAltMode()
        
        self.resetShutdownTimer()
        self.incrementNbOperations()
        
     # Callback for switches (play/pause, skip forward/backward)
    def callbackControlSwitch(self, channel):
        logging.debug("Switch {} pressed (channel {:d}, alt. mode: {}, shift mode: {})".format(self.switches[channel], 
                                                                               channel, 
                                                                               "ON" if self.isAltModeOn() else "OFF",
                                                                               "ON" if self.isShiftModeOn() else "OFF"))
        print("Edge detected on channel {:d} [Switch ID: {}, alt. mode: {}, shift mode: {}]".format(channel, 
                                                                                    self.switches[channel], 
                                                                                    "ON" if self.isAltModeOn() else "OFF",
                                                                                    "ON" if self.isShiftModeOn() else "OFF"))

        if self.queue is not None:
            try:
                if self.isShiftModeOn():
                    if self.switches[channel] == self.playSwitch:
                        self.deactivateShiftMode()
                else:
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
            
        self.resetShutdownTimer()
        self.incrementNbOperations()

    # Start procedure to switch off the pi under certain conditions
    def initiateSwitchOff(self):
        logging.debug("Initiating switch off (Key combination Mode + Back)") 
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
            logging.error("Problem initiating switch off")
        
    # If the conditions are fulfilled, switch off the pi
    def completeSwitchOff(self):
        logging.debug("Attempting to complete switch off (Key combination Mode + Back)") 

        # Make sure the number of operations has not changed since initiating the switch off procedure
        if self.nbOperations != self.switchOffCurrentNbOperations + 1 \
        and self.nbOperations != 1: # Case where self.nbOperations has been reset
            logging.debug("Canceling switch off (Key combination Mode + Back): Other keys have been pressed in the meantime") 
            return
        
        # Make sure the key combination is still being pressed
        if GPIO.input(self.modePort) != GPIO.LOW or GPIO.input(self.backPort) != GPIO.LOW:
            logging.debug("Canceling switch off (Key combination Mode + Back): Key combination no longer pressed") 
            return
        
        # All the conditions are fulfilled: Send switch off signal
        logging.debug("Mode and Back pressed for {} seconds: Sending signal to shut down the pi".format(self.switchOffTimePeriod))

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
        
            
                    
    def run(self, stopper=None, queue=None):         
        try:
            logging.info("Starting main loop")  
            print("Reacting to interrupts from switches")
            self.queue = queue
            logging.info("Starting timer to monitor activity and shut down the pi after a given idle time") 
            self.shutdownTimer.start()
              
            while True:
                sleep(0.1)  # sleep 100 msec       
                                                    # because of threading make sure no thread
                                                    # changes value until we get them
                                                    # and reset them
                                                    
                self.processRotary()

                if self.stopRequested:
                    logging.debug("Requesting stop")
                    break

                if stopper is not None:
                    try:
                        if stopper.is_set():
                            break
                    except:
                        pass
                    
                self.blinkLedsForShift()
 
        except KeyboardInterrupt:
            logging.info("Stop (Ctrl-C from main loop)") 
            print("Stop (Ctrl-C)")
        finally:
            # clean up GPIO on exit  
            logging.debug("Cleaning up GPIO")
            GPIO.cleanup()
#            logging.debug("Canceling shutdown timer")
#            try:
#                self.shutdownTimer.join()
#            except:
#                pass
#            logging.debug("Canceling switch off timer")
#            try:
#                self.switchOffTimer.join()
#            except:
#                pass
            logging.debug("Over.")
            
        logging.debug("Bye!")

    def requestStop(self):
        self.stopRequested = True

if __name__ == '__main__':
    # Logging
    logging.basicConfig(filename='userInterface.log', 
                        level=logging.DEBUG, 
                        format='%(asctime)s %(levelname)s:%(message)s', 
                        datefmt='%Y-%m-%d %H:%M:%S')
        
    logging.info("Creating instance of UserInterface") 
    ui = UserInterface()
    try:
        ui.run()
    except KeyboardInterrupt:
        logging.info("Stop (Ctrl-C from __main__)") 
        print("Stop (Ctrl-C) [from main]")
        ui.requestStop()
