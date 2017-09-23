#!/usr/bin/env python3.4
import RPi.GPIO as GPIO 
from collections import deque
import threading
from time import sleep
import logging
    
    
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
    
    def initSwitches(self):
        # Switches: {Port, Name}
        self.switches = { 
                    14: "Switch 1",
                    15: "Switch 4",
                    18: "Switch 7",
                    23: "Switch 10",
                    24: "Switch 2",
                    25: "Switch 5",
                    8: "Switch 8",
                    7: "Switch 11",
                    12: "Switch 3",
                    16: "Switch 6",
                    20: "Switch 9",
                    21: "Switch 12",
                    5: "Play/Pause",
                    11: "Forward",
                    9: "Back",
                    17: "Bank",
                    27: "Mode"
                    }
        # Special switches
        self.bankSwitch = "Bank" # Switch to a different playlist bank
        self.modeSwitch = "Mode" # Hold down to activate alternate mode
        self.modePort = 0 # Port for the mode switch
        # Checks (Bank and Mode switch must be defined)
        assert(self.bankSwitch in self.switches.values())
        assert(self.modeSwitch in self.switches.values())
        # Indicate whether alternate mode is on (upon holding down the Mode button)
        self.altMode = False
        # Set ports as input with pull-up resistor
        for s, name in self.switches.items():
            GPIO.setup(s, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            # Mark port for the Mode switch
            if name == self.modeSwitch:
                self.modePort = s
        # Define callbacks for switch presses
        for s in self.switches:
            GPIO.add_event_detect(s, GPIO.FALLING, callback=self.callbackSwitch, bouncetime=300)  

    def initLeds(self):
        # LEDs for the different playlist banks: Ports and names
        self.ledPorts = [6, 19, 13, 26]
        self.ledNames = ["Bank A", "Bank B", "Bank C", "Bank D"]
        # Initial state of the bank leds (1st one ON)
        ledStates = [GPIO.HIGH, GPIO.LOW, GPIO.LOW, GPIO.LOW]
        # Checks (the lists have to have the same number of elements)
        assert(len(self.ledPorts) == len(self.ledNames))
        assert(len(ledStates) == len(self.ledNames))
        # LEDs: {Port, Name}
        leds = dict(zip(self.ledPorts, self.ledNames))
        # Name of the LED which is ON by default at startup
        defaultLed = "Bank A"
        assert(defaultLed in self.ledNames)
        activeLed = self.ledPorts[self.ledNames.index(defaultLed)]
        activeLedName = leds[activeLed]
        # Set the corresponding ports as output with state HIGH for the 1st one
        for l, name in leds.items():
            GPIO.setup(l, GPIO.OUT)
            GPIO.output(l, GPIO.HIGH if name == defaultLed else GPIO.LOW)

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


    # Increment active bank (cycle through leds)
    def incrementBank(self, reverseOrder=False):    
        activeLeds = 0
        increment = 1 if not reverseOrder else -1
        ledStates = deque()
        for l in self.ledPorts:
            ledStates.append(GPIO.input(l))
            if ledStates[-1] == GPIO.HIGH:
                activeLeds = activeLeds + 1
        if activeLeds == 0:
            ledStates[0] = GPIO.HIGH
        ledStates.rotate(increment)
        for l in self.ledPorts:
            GPIO.output(l, ledStates[self.ledPorts.index(l)])
    
    # Mode switch
    def activateMode(self):
        self.altMode = True
    def isAltModeOn(self):
        if self.altMode and GPIO.input(self.modePort) == GPIO.LOW:
            return True 
        else:
            self.altMode = False
            return False
    def isAltModeOff(self):
        return not self.isAltModeOn()
    
    # Callback for switches 
    def callbackSwitch(self, channel):
        logging.debug("Switch {} pressed (channel {:d}, alt. mode: {})".format(self.switches[channel], 
                                                                               channel, 
                                                                               "ON" if self.isAltModeOn() else "OFF"))
        print("Edge detected on channel {:d} [Switch ID: {}, alt. mode: {}]".format(channel, 
                                                                                    self.switches[channel], 
                                                                                    "ON" if self.isAltModeOn() else "OFF"))
        if self.switches[channel] == self.bankSwitch:
            self.incrementBank(self.isAltModeOn())
        elif self.switches[channel] == self.modeSwitch:
            self.activateMode()
        
    
    def run(self, stopper=None):            
        try:
            logging.info("Starting main loop")  
            print("Reacting to interrupts from switches")  
            while True:
                sleep(0.1)  # sleep 100 msec       
                                                    # because of threading make sure no thread
                                                    # changes value until we get them
                                                    # and reset them
                                                    
                self.rotaryLock.acquire()  # get lock for rotary switch
                self.newCounter = self.rotaryCounter  # get counter value
                self.rotaryCounter = 0  # RESET IT TO 0
                self.rotaryLock.release()  # and release lock
                        
                if self.newCounter != 0:  # Counter has CHANGED
                    self.volume = self.volume + self.newCounter * abs(self.newCounter)  # Decrease or increase volume 
                    if self.volume < 0:  # limit volume to 0...100
                        self.volume = 0
                    if self.volume > 100:  # limit volume to 0...100
                        self.volume = 100
                    logging.debug("New volume: {:d}".format(self.volume))
                    print("self.newCounter: {:d}; self.volume = {:d}".format(self.newCounter, self.volume))  # some test print

                if self.stopRequested:
                    logging.debug("Requesting stop")
                    break

                if stopper is not None:
                    try:
                        if stopper.is_set():
                            break
                    except:
                        pass
 
        except KeyboardInterrupt:
            logging.info("Stop (Ctrl-C from main loop)") 
            print("Stop (Ctrl-C)")
        finally:
            # clean up GPIO on exit  
            logging.debug("Cleaning up GPIO") 
            GPIO.cleanup()

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
