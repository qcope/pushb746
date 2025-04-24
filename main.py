import _thread
from machine import Pin
from utime import sleep
from collections import deque
import time

BROWN_WIRE  =   "GP16"
BLUE_WIRE   =   "GP17"
ORANGE_WIRE =   "GP18"
GREY_WIRE   =   "GP19"

RELAY_LOOP  =   "GP20"
RELAY_MIC   =   "GP21"
RELAY_EAR   =   "GP22"
RELAY_HOOK  =   "GP26" # will use the relay to go off hook, even with the handset in the cradle

BUTTON_1    =   "GP27"
BUTTON_2    =   "GP28"

MAX_QUEUE = 100 # 100 digit queue... more than enough
BOUNCE_TIME = 500 # 500ms second debounce time
HOOK_FLASH_TIME = 0.5 # 500ms hook flash time

#globals
button1 = Pin(BUTTON_1, Pin.IN, Pin.PULL_UP)
button2 = Pin(BUTTON_2, Pin.IN, Pin.PULL_UP)
dial_queue = deque("", MAX_QUEUE)
shared_state = {"all_done": False, "dialler_running": False}  # Use a shared dictionary for thread-safe access
button1_pressed = False
button1_time = 0
button2_pressed = False
button2_time = 0
on_hook_dialling_enabled = False
buttons_enabled = False

led         = Pin("LED", Pin.OUT)
relay_loop  = Pin(RELAY_LOOP, Pin.OUT)
relay_mic   = Pin(RELAY_MIC, Pin.OUT)
relay_ear   = Pin(RELAY_EAR, Pin.OUT)
relay_hook  = Pin(RELAY_HOOK, Pin.OUT)
 # these relays are active low
relay_loop.on()    
relay_mic.on()
relay_ear.on()
relay_hook.on()
# now they are all set to off !

def reset_pins():
    # Reset all keyboard pins to input
    for i in range(16, 19):
        pin = Pin("GP" + str(i), Pin.IN, Pin.PULL_UP)

def pin_test(output_pin_name, input_pin_name):
    reset_pins()
    output_pin = Pin(output_pin_name, Pin.OUT)
    input_pin =  Pin(input_pin_name, Pin.IN, Pin.PULL_UP)
    output_pin.off() # make 0

    time.sleep_us(10)
    value=input_pin.value()
    if value == 0:
        return 1
    return 0

def leg_b_test_1():
    return pin_test(BROWN_WIRE, BLUE_WIRE)

def leg_b_test_2():
    return pin_test(BLUE_WIRE, BROWN_WIRE)

def leg_a_test_1():
    return pin_test(BLUE_WIRE, ORANGE_WIRE)

def leg_a_test_2():
    return pin_test(ORANGE_WIRE, BLUE_WIRE)

def read_keyboard(): # We'll perform the leg tests and determine which key is pressed or if none, return ?
        value = '?'
        leg_a_1 = leg_a_test_1()
        leg_a_2 = leg_a_test_2()
        leg_b_1 = leg_b_test_1()
        leg_b_2 = leg_b_test_2()    

        if leg_b_1 and not leg_b_2 and not leg_a_1 and not leg_a_2:
            value = '1'
        elif not leg_b_1 and not leg_b_2 and not leg_a_1 and leg_a_2:
            value = '2'
        elif leg_b_1 and not leg_b_2 and not leg_a_1 and leg_a_2:
            value = '3'
        elif leg_b_1 and leg_b_2 and not leg_a_1 and not leg_a_2:
            value = '4'
        elif not leg_b_1 and leg_b_2 and not leg_a_1 and leg_a_2:
            value = '5'
        elif leg_b_1 and leg_b_2 and not leg_a_1 and leg_a_2:
            value = '6'
        elif leg_b_1 and not leg_b_2 and leg_a_1 and not leg_a_2:
            value = '7'
        elif not leg_b_1 and not leg_b_2 and leg_a_1 and leg_a_2:
            value = '8'
        elif leg_b_1 and not leg_b_2 and leg_a_1 and leg_a_2:
            value = '9'
        elif not leg_b_1 and leg_b_2 and leg_a_1 and leg_a_2:
            value = '0'

        return value

def thread_dial():
    # This function will run in a separate thread to handle dialing
    # bit messy here but with the new ability for on hook dialing
    # we need to check if we should be enabling the microphone or not
    print("Dialer Started")
    global dial_queue, relay_loop, relay_mic, relay_ear, shared_state, led, on_hook_dialling_enabled

    enable_buttons()
    led.off()
    #put the relays in the default state
    relay_loop.on() # relay will be not energised. Relay wired for the loop to be connected. This is the default for a dialer
    relay_mic.on()  # which is non energised. The contacts are wired to be disconnected in this state. Short for mic not enabled.
    relay_ear.on()  # as above... not energised and ear not shorted out.

    shared_state["dialler_running"] = True  # Update the shared state
    while (not shared_state["all_done"]) or (len(dial_queue) > 0):  # Access the shared state
        if len(dial_queue) > 0: # we have at least one digit in the queue
            disable_buttons()
            relay_mic.off() # energise relay, short circuit the mic
            relay_ear.off() # energise relay, short circuit the ear
            digit = dial_queue.popleft()
            print("\tDialing: ", digit)
            if digit == 0:
                digit = 10
            for i in range(digit):
                led.on()
                relay_loop.off() # energise relay... contacts open, as wired
                sleep(0.066)

                led.toggle()
                relay_loop.on() # de-energise the relay, contacts close
                sleep(0.033)
            sleep(0.8)  # 700 is the minimum inter digit delay. Don't bother to delay, if no more digits in queue
            enable_buttons()  
        else:
            
            if not on_hook_dialling_enabled:
                relay_mic.on() # de-energise relay, connect the mic
            relay_ear.on() # de-energise relay, connect the ear
            sleep(0.1) # no point in hammering the CPU
            led.toggle()
    shared_state["dialler_running"] = False  # Update the shared state
    print("Dialer Done")

def button1_press_handler(pin):
    global button1_pressed,button1_time,BOUNCE_TIME
    now = time.ticks_ms()
    if now - button1_time < BOUNCE_TIME:
        return
    button1_pressed = True
    button1_time = now

def button2_press_handler(pin):
    global button2_pressed,button2_time,BOUNCE_TIME
    now = time.ticks_ms()
    if now - button2_time < BOUNCE_TIME:
        return
    button2_pressed = True
    button2_time = now
    
def enable_buttons():
    global button1,button2,buttons_enabled

    if buttons_enabled:
        return
    # Set up the buttons as inputs with pull-up resistors
    print("Setting up buttons ",BUTTON_1, BUTTON_2)
    # Set up interrupts for button presses
    button1.irq(trigger=Pin.IRQ_FALLING, handler=button1_press_handler)
    button2.irq(trigger=Pin.IRQ_FALLING, handler=button2_press_handler)
    buttons_enabled = True

def disable_buttons():
    global button1,button2,buttons_enabled
    if not buttons_enabled:
        return
    # Disable the button interrupts
    print("Disabling buttons ",BUTTON_1, BUTTON_2)
    button1.irq(trigger=0)
    button2.irq(trigger=0)
    buttons_enabled = False

def debounce_buttons():
    global button1_pressed, button2_pressed
    # Debounce the buttons
    if button1_pressed:
        sleep(0.1)  # Debounce delay
        if button1.value() == 1:
            button1_pressed = False
    if button2_pressed:
        sleep(0.1)  # Debounce delay
        if button2.value() == 1:
            button2_pressed = False

def read_buttons():
    global button1_pressed, button2_pressed, on_hook_dialling_enabled,relay_hook,relay_mic

    debounce_buttons()

    if button1_pressed:
        # button 1 has been pressed... Let's disable the microphone and "lift the receiver"
        # we have a momentary button... so first time pressed... we do the logic to support on hook dialing
        # next time through.... we disable this.
        if not on_hook_dialling_enabled:
            # enable the on hook dialing
            print("Enabling on hook dialing")
            relay_mic.off()
            relay_hook.off()
            print("Done")

            on_hook_dialling_enabled = True
        else:
            # disable the on hook dialing
            print("Disabling on hook dialing")
            relay_mic.on()
            relay_hook.on()
            print("Done")

            on_hook_dialling_enabled = False

        button1_pressed = False
    if button2_pressed:
        # buttone 2 has been pressed... Let's do a hook flash.... to get a dial tone
        # logic goes here!
        print("Hook Flash")
        relay_loop.off()
        sleep(HOOK_FLASH_TIME)
        relay_loop.on()
        print("Hook Flash Done")
        button2_pressed = False

print("Starting")
enable_buttons()

print("Starting dialer thread")

_thread.start_new_thread(thread_dial, ())
old_value = '?'

while True:
    try:
        # first read the numeric keypad
        value = read_keyboard()
        if value != old_value: # something to do here...
            if value.isdigit(): 
                print ("Key: ", value)
                dial_queue.append(int(value))
            old_value = value
            sleep(0.2)  # Debounce delay... crude!
        else:   
            sleep(0.1)  # no point in hammering the CPU
        # now read the buttons
        read_buttons()
    except KeyboardInterrupt:
        break

shared_state["all_done"] = True  # Update the shared state
print("Waiting for dialer to finish ")
while shared_state["dialler_running"]:  # Access the shared state
    sleep(0.1)


print("Finished")
