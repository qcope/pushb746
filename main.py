from machine import Pin
from utime import sleep
from collections import deque
import _thread
import time

BROWN_WIRE  =   "GP16"
BLUE_WIRE   =   "GP17"
ORANGE_WIRE =   "GP18"
GREY_WIRE   =   "GP19"

RELAY_LOOP  =   "GP20"
RELAY_MIC   =   "GP21"
RELAY_EAR   =   "GP22"
RELAY_4     =   "GP23"

MAX_QUEUE = 100 # 100 digit queue... more than enough
dial_queue = deque("", MAX_QUEUE)
shared_state = {"all_done": False, "dialler_running": False}  # Use a shared dictionary for thread-safe access

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
    print("Dialer Started")
    led = Pin("LED", Pin.OUT)
    led.off()
    relay_loop = Pin(RELAY_LOOP, Pin.OUT)
    relay_loop.on()
    relay_mic = Pin(RELAY_MIC, Pin.OUT)
    relay_mic.on()
    relay_ear = Pin(RELAY_EAR, Pin.OUT)
    relay_ear.on()

    shared_state["dialler_running"] = True  # Update the shared state
    while (not shared_state["all_done"]) or (len(dial_queue) > 0):  # Access the shared state
        if len(dial_queue) > 0: # we have at least one digit in the queue
            relay_mic.off() # energise relay, disconnect the mic
            relay_ear.off() # energise relay, disconnect the ear
            digit = dial_queue.popleft()
            print("\tDialing: ", digit)
            if digit == 0:
                digit = 10
            for i in range(digit):
                led.toggle()
                relay_loop.toggle()
                sleep(0.066)

                led.toggle()
                relay_loop.toggle()
                sleep(0.033)
            sleep(0.8)  # 700 is the minimum inter digit delay. Don't bother to delay, if no more digits in queue
              
        else:
            relay_mic.on() # de-energise relay, connect the mic
            relay_ear.on() # de-energise relay, connect the ear
    shared_state["dialler_running"] = False  # Update the shared state
    print("Dialer Done")


print("Starting")

_thread.start_new_thread(thread_dial, ())
old_value = '?'

while True:
    try:
        value = read_keyboard()
        if value != old_value: # something to do here...
            if value.isdigit(): 
                print ("Key: ", value)
                dial_queue.append(int(value))
            old_value = value
            sleep(0.2)  # Debounce delay... crude!
        else:   
            sleep(0.1)  # no point in hammering the CPU
    except KeyboardInterrupt:
        break

shared_state["all_done"] = True  # Update the shared state
print("Waiting for dialer to finish ")
while shared_state["dialler_running"]:  # Access the shared state
    sleep(0.1)


print("Finished")