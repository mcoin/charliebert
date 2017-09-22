#!/usr/bin/env python3.4
import RPi.GPIO as GPIO 
from collections import deque
GPIO.setmode(GPIO.BCM)  

# Switches 
#GPIO.setup(21, GPIO.IN, pull_up_down=GPIO.PUD_UP)  
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
#GPIO.setup(12, GPIO.OUT)
#GPIO.output(12, GPIO.HIGH)
ledPorts = [6, 19, 13, 26]
ledNames = ["Bank A", "Bank B", "Bank C", "Bank D"]
ledStates = [GPIO.HIGH, GPIO.LOW]
assert(len(ledPorts) == len(ledNames))
leds = dict(zip(ledPorts, ledNames))
defaultLed = "Bank A"
assert(defaultLed in ledNames)
activeLed = ledPorts[ledNames.index(defaultLed)]
#activeLedName = defaultLed
activeLedName = leds[activeLed]
#print("Main: active led <{:d}>".format(activeLed))
for l, name in leds.items():
    GPIO.setup(l, GPIO.OUT)
    GPIO.output(l, GPIO.HIGH if name == defaultLed else GPIO.LOW)
        
# Increment active bank (cycle through leds)
def incrementBank():
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
    print("Edge detected on channel {:d} [Switch ID: {}]".format(channel, switches[channel]))
    if switches[channel] == bankSwitch:
        incrementBank()
    
#GPIO.add_event_detect(20, GPIO.FALLING, callback=callbackSwitch, bouncetime=300)  
for s in switches:
    GPIO.add_event_detect(s, GPIO.FALLING, callback=callbackSwitch, bouncetime=300)  
  
try:  
    print("Reacting to interrupts from switches")  
    while True:
        pass 
  
except KeyboardInterrupt:
    print("Stop (Ctrl-C)")
finally:
    # clean up GPIO on exit  
    GPIO.cleanup()
