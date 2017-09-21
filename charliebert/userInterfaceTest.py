#!/usr/bin/env python3.4
import RPi.GPIO as GPIO  
GPIO.setmode(GPIO.BCM)  

# Switches 
GPIO.setup(20, GPIO.IN, pull_up_down=GPIO.PUD_UP)  
GPIO.setup(21, GPIO.IN, pull_up_down=GPIO.PUD_UP)  
  
  
# Callback for switches 
def callbackSwitch(channel):  
    print("Edge detected on channel %d", channel)
    
GPIO.add_event_detect(20, GPIO.FALLING, callback=callbackSwitch, bouncetime=300)  
GPIO.add_event_detect(21, GPIO.FALLING, callback=callbackSwitch, bouncetime=300)  
  
try:  
    print("Reacting to interrupts from switches")  
    while True:
        pass 
  
except KeyboardInterrupt:  
    GPIO.cleanup()       # clean up GPIO on CTRL+C exit  
GPIO.cleanup()           # clean up GPIO on normal exit 