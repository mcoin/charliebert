#!/usr/bin/env python3.4
import RPi.GPIO as GPIO 
GPIO.setmode(GPIO.BCM)  

# Switches 
#GPIO.setup(21, GPIO.IN, pull_up_down=GPIO.PUD_UP)  
switches = { 20: "Switch 1", 21: "Switch 2"}
bankSwitch = "Switch 1"
assert(bankSwitch in switches.values())
for s in switches:
    GPIO.setup(s, GPIO.IN, pull_up_down=GPIO.PUD_UP)  

# LEDs
#GPIO.setup(12, GPIO.OUT)
#GPIO.output(12, GPIO.HIGH)
ledPorts = [12, 16]
ledNames = ["LED1", "LED2"]
assert(ledPorts.len == ledNames.len)
leds = dict(zip(ledPorts, ledNames))
defaultLed = "LED 1"
assert(defaultLed in leds.values())
activeLed = ledPorts[ledNames.index(defaultLed)]
for l, name in leds:
    GPIO.setup(l, GPIO.OUT)
    GPIO.output(l, GPIO.HIGH if name == defaultLed else GPIO.LOW)
        
# Increment active bank (cycle through leds)
def incrementBank():
    activeLedIndex = ledPorts.index(activeLed)
    GPIO.output(activeLed, GPIO.LOW)
    activeLedIndex = activeLedIndex + 1
    activeLed = ledPorts[activeLedIndex]
    GPIO.output(activeLed, GPIO.HIGH)

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