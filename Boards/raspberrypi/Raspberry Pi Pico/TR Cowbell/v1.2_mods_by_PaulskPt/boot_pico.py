import board
import digitalio
import storage

up_btn = digitalio.DigitalInOut(board.GP21)
up_btn.direction = digitalio.Direction.INPUT # BUTTON 1
up_btn.pull = digitalio.Pull.UP

storage.remount("/", not up_btn.value)   
# storage.remount("/", False) # If you don't want to press the UP-button (BUTTON 1) at boot, use this line
