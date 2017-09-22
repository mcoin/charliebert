#!/usr/bin/env python3.4
import RPi.GPIO as GPIO 
from collections import deque
import threading
from time import sleep

GPIO.setwarnings(True)
GPIO.setmode(GPIO.BCM)  

# Encoder input A
Enc_A = 10                  
# Encoder input B
Enc_B = 22 

Rotary_counter = 0               # Start counting from 0
Current_A = 1                    # Assume that rotary switch is not 
Current_B = 1                    # moving while we init software

LockRotary = threading.Lock()        # create lock for rotary switch


# initialize interrupt handlers
def init():
    # define the Encoder switch inputs
    GPIO.setup(Enc_A, GPIO.IN)                 
    GPIO.setup(Enc_B, GPIO.IN)
    # setup callback thread for the A and B encoder 
    # use interrupts for all inputs
    GPIO.add_event_detect(Enc_A, GPIO.RISING, callback=rotary_interrupt) # NO bouncetime 
    GPIO.add_event_detect(Enc_B, GPIO.RISING, callback=rotary_interrupt) # NO bouncetime 
    return


# Rotarty encoder interrupt:
# this one is called for both inputs from rotary switch (A and B)
def rotary_interrupt(A_or_B):
    global Rotary_counter, Current_A, Current_B, LockRotary
    # read both switches
    Switch_A = GPIO.input(Enc_A)
    Switch_B = GPIO.input(Enc_B)
    # now check if state of A or B has changed
    # if not that means that bouncing caused it
    if Current_A == Switch_A and Current_B == Switch_B:        # Same interrupt as before (Bouncing)?
        return                                        # ignore interrupt!

    Current_A = Switch_A                                # remember new state
    Current_B = Switch_B                                # for next bouncing check


    if (Switch_A and Switch_B):                        # Both one active? Yes -> end of sequence
        LockRotary.acquire()                        # get lock 
        if A_or_B == Enc_B:                            # Turning direction depends on 
            Rotary_counter += 1                        # which input gave last interrupt
        else:                                        # so depending on direction either
            Rotary_counter -= 1                        # increase or decrease counter
        LockRotary.release()                        # and release lock
    return        
        
# Increment active bank (cycle through leds)
def incrementBank():
    global ledPorts

    activeLeds = 0
    ledStates = deque()
    for l in ledPorts:
        ledStates.append(GPIO.input(l))
        if ledStates[-1] == GPIO.HIGH:
            activeLeds = activeLeds + 1
    if activeLeds == 0:
        ledStates[0] = GPIO.HIGH
    ledStates.rotate(1)
    for l in ledPorts:
        GPIO.output(l, ledStates[ledPorts.index(l)])


# Callback for switches 
def callbackSwitch(channel):  
    global switches, bankSwitch

    print("Edge detected on channel {:d} [Switch ID: {}]".format(channel, switches[channel]))
    if switches[channel] == bankSwitch:
        incrementBank()
    

def main():    
    global switches, bankSwitch, ledPorts
    global Rotary_counter, LockRotary
    
    # Switches 
    switches = { 
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
    bankSwitch = "Bank"
    assert(bankSwitch in switches.values())
    for s in switches:
        GPIO.setup(s, GPIO.IN, pull_up_down=GPIO.PUD_UP)  
    
    # LEDs
    ledPorts = [6, 19, 13, 26]
    ledNames = ["Bank A", "Bank B", "Bank C", "Bank D"]
    ledStates = [GPIO.HIGH, GPIO.LOW]
    assert(len(ledPorts) == len(ledNames))
    leds = dict(zip(ledPorts, ledNames))
    defaultLed = "Bank A"
    assert(defaultLed in ledNames)
    activeLed = ledPorts[ledNames.index(defaultLed)]
    activeLedName = leds[activeLed]
    
    for l, name in leds.items():
        GPIO.setup(l, GPIO.OUT)
        GPIO.output(l, GPIO.HIGH if name == defaultLed else GPIO.LOW)
     
    for s in switches:
        GPIO.add_event_detect(s, GPIO.FALLING, callback=callbackSwitch, bouncetime=300)  
    

    Volume = 0                                    # Current Volume    
    NewCounter = 0                                # for faster reading with locks
                        
    init()
    
    try:  
        print("Reacting to interrupts from switches")  
        while True:
            sleep(0.1)                          # sleep 100 msec       
                                                # because of threading make sure no thread
                                                # changes value until we get them
                                                # and reset them
                                                
            LockRotary.acquire()                    # get lock for rotary switch
            NewCounter = Rotary_counter            # get counter value
            Rotary_counter = 0                        # RESET IT TO 0
            LockRotary.release()                    # and release lock
                    
            if (NewCounter !=0):                    # Counter has CHANGED
                Volume = Volume + NewCounter*abs(NewCounter)    # Decrease or increase volume 
                if Volume < 0:                        # limit volume to 0...100
                    Volume = 0
                if Volume > 100:                    # limit volume to 0...100
                    Volume = 100
                print("NewCounter: {:d}; Volume = {:d}".format(NewCounter, Volume))            # some test print
      
    except KeyboardInterrupt:
        print("Stop (Ctrl-C)")
    finally:
        # clean up GPIO on exit  
        GPIO.cleanup()


if __name__ == '__main__':
    main()
