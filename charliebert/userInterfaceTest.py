#!/usr/bin/env python3.4
import RPi.GPIO as GPIO  
GPIO.setmode(GPIO.BCM)  

# Switches 
#GPIO.setup(21, GPIO.IN, pull_up_down=GPIO.PUD_UP)  
switches = { 20: "Switch 1", 21: "Switch 2"}
for s in switches:
    GPIO.setup(s, GPIO.IN, pull_up_down=GPIO.PUD_UP)  
  
# LEDs
GPIO.setup(12, GPIO.OUT)
GPIO.output(12, GPIO.HIGH)
GPIO.setup(16, GPIO.OUT)
GPIO.output(16, GPIO.HIGH)

# Callback for switches 
def callbackSwitch(channel):  
    print("Edge detected on channel {:d} [Switch ID: {}]".format(channel, switches[channel]))
    
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