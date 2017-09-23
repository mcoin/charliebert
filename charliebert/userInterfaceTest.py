#!/usr/bin/env python3.4
import RPi.GPIO as GPIO 
from collections import deque
import threading
from time import sleep
import logging
    
    
class UserInterface:
    
    def __init__(self):
        # GPIO settings
        GPIO.setwarnings(True)
        GPIO.setmode(GPIO.BCM)  

        # Logging
        logging.basicConfig(filename='userInterface.log',level=logging.DEBUG)
        logging.info("Starting instance of UserInterface")
        
        # Switches 
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
        self.bankSwitch = "Bank"
        assert(self.bankSwitch in self.switches.values())
        self.modeSwitch = "Mode"
        self.modePort = 0
        assert(self.modeSwitch in self.switches.values())
        # Indicate whether alternate mode is on (upon holding down the Mode button)
        self.altMode = False
        
        for s, name in self.switches.items():
            GPIO.setup(s, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            if name == self.modeSwitch:
                self.modePort = s

        
        # LEDs
        self.ledPorts = [6, 19, 13, 26]
        self.ledNames = ["Bank A", "Bank B", "Bank C", "Bank D"]
        ledStates = [GPIO.HIGH, GPIO.LOW, GPIO.LOW, GPIO.LOW]
        assert(len(self.ledPorts) == len(self.ledNames))
        assert(len(ledStates) == len(self.ledNames))
        leds = dict(zip(self.ledPorts, self.ledNames))
        defaultLed = "Bank A"
        assert(defaultLed in self.ledNames)
        activeLed = self.ledPorts[self.ledNames.index(defaultLed)]
        activeLedName = leds[activeLed]
        
        for l, name in leds.items():
            GPIO.setup(l, GPIO.OUT)
            GPIO.output(l, GPIO.HIGH if name == defaultLed else GPIO.LOW)
         
        for s in self.switches:
            GPIO.add_event_detect(s, GPIO.FALLING, callback=self.callbackSwitch, bouncetime=300)  
        
    
        # Rotary encoder
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
    
	self.stopRequested = False
    
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
        print("Edge detected on channel {:d} [Switch ID: {}, alt. mode: {}]".format(channel, 
                                                                                    self.switches[channel], 
                                                                                    "ON" if self.isAltModeOn() else "OFF"))
        if self.switches[channel] == self.bankSwitch:
            self.incrementBank(self.isAltModeOn())
        elif self.switches[channel] == self.modeSwitch:
            self.activateMode()
        
    
    def run(self):            
        try:  
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
                    print("self.newCounter: {:d}; self.volume = {:d}".format(self.newCounter, self.volume))  # some test print

                if self.stopRequested:
        		   break
 
        except KeyboardInterrupt:
            print("Stop (Ctrl-C)")
        finally:
            # clean up GPIO on exit  
            GPIO.cleanup()

    def requestStop(self):
        self.stopRequested = True

if __name__ == '__main__':
    ui = UserInterface()
    try:
        ui.run()
    except KeyboardInterrupt:
        print("Stop (Ctrl-C) [from main]")
	ui.requestStop()
