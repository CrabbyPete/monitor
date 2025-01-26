#!/usr/bin/env python3
import os
import time
import pigpio
import subprocess

# Local imports
from log        import log
from status     import state

MIN_DUTY = 0
MAX_DUTY = 1000000

PUMP_CHANNEL = 24
PUMP_FREQ = 10000
PUMP_DUTY = 126         # Percentage of 256 126 ~= 50%

BUTTON_1_CHANNEL = 27
BUTTON_2_CHANNEL = 22

LED_CHANNEL = 12        # PWM LED channel
LED_FREQUENCY = 80000

IR_LED_CHANNEL = 6
RED_LED_CHANNEL = 13

pig = pigpio.pi()


def get_serial():
    """
    Get the system serial number of this Pi
    :return: str: serial number
    """
    with os.popen("cat /proc/cpuinfo | grep Serial | cut -d ' ' -f 2 | md5sum | cut -d ' ' -f 1") as fp:
        serial = fp.read().splitlines()[0]
    return serial


def red_light(command):
    """
    Turn on and off red light
    :param command: str 'on'|'off
    :return:
    """
    value = 1 if command == 'on' else 0
    pig.write(RED_LED_CHANNEL, value)


def ir_led(command):
    """
    Turn on and off IR LED
    :param command: str: 'on'|'off
    :return:
    """
    value = 1 if command == 'on' else 0
    pig.write(IR_LED_CHANNEL, value)


def lights(command, *values):
    """
    Turn on and off the leds
    :param command: str: on, off, boost, or integer value
    :param values: option value for a given command
    :return:
    """
    log.info("lights {} {}".format(command, values))

    # Current state has to be a percentage of the maximum duty cycle 100000.
    value = 0
    if values:
        if isinstance(values[0], str):
            try:
                value = int(values[0])
            except TypeError:
                value = 0
        elif isinstance(values[0], int):
            value = values[0]

    if command == 'on':
        try:
            value = int(state.previous_lights[0])
            if not value:
                value = 50
        except AttributeError:
            value = 50

    elif command == 'boost':
        value = 100

    elif command == 'off':
        state.previous_lights = state.lights[0]
        value = 0

    elif command == 'adjust':
        # Adjust the current value by percent of current value # Note the app is sending this after an 'off'
        current, _ = state.lights
        current = int(current) + value
        value = min(max(current, 0), 100)

    elif command == 'set':
        # Set the value to set percentage of duty cylce
        value = min(max(value, 0), 100)

    elif command == 'blink' and value > 0:
        # Blink the lights value times
        current_state = int(state.lights[0])

        pig.set_PWM_dutycycle(LED_CHANNEL, 0)
        for v in range(value):
            pig.hardware_PWM(LED_CHANNEL, LED_FREQUENCY, MAX_DUTY)
            time.sleep(1)

            pig.hardware_PWM(LED_CHANNEL, LED_FREQUENCY, MIN_DUTY)
            time.sleep(1)
        value = int(MAX_DUTY * current_state/100.)
        pig.hardware_PWM(LED_CHANNEL, LED_FREQUENCY, value)
        return current_state

    elif command == 'transition' and len(values) == 3:
        percent = int(values[1])
        increments = int(values[2])
        current = int(state.lights[0])
        times = 0

        while True:
            if percent > 0 and current >= value:
                break
            elif percent < 0 and current <= value:
                break

            current += percent

            # Don't go out of range
            if current > 100:
                current = 100
            if current < 0:
                current = 0

            lights('set', current)
            log.info("Current:{}".format(current))

            # Make sure you don't wind up in an infinite loop
            time.sleep(increments)
            times = times + 1
            if times >= 100:
                break
        return current

    current_state = int(state.lights[0])
    state.lights = current_state

    return current_state


def motor():
    """
    Get the current water level
    :return:
    """
    # log.info("Reading water level")
    pass


def i2c_scan():
    """
    Scan the I2C bus and see what's there
    """
    bus_addresses = []
    for bus in range(2):
        for x in range(0x08, 0x79):
            handle = pig.i2c_open(bus, x)
            if handle:
                s = pig.i2c_read_byte(handle)
                if s >= 0:
                    bus_addresses.append(x)
                pig.i2c_close(handle)
    return bus_addresses


def tmp102(bus=1, address=0x48):
    """
    Read the tmp102 temperature and humidity sensor
    :param bus: I2C bus
    :param address: I2C address of the device
    :return set temperature humidity
    """
    def twos_comp(val, bits):
        if (val & (1 << (bits - 1))) != 0:
            val = val - (1 << bits)
        return val

    handle = pig.i2c_open(bus, address)

    # Read the configuration block
    _, data = pig.i2c_read_i2c_block_data(handle, 0x01, 2)

    # Set to 4 Hz sampling (CR1, CR0 = 0b10)
    data[1] = data[1] & 0b00111111
    data[1] = data[1] | (0b10 << 6)

    # Write 4 Hz sampling back to CONFIG
    pig.i2c_write_i2c_block_data(address, 0x01, data)

    _, val = pig.i2c_read_i2c_block_data(handle,0x00,2)
    temp_c = (val[0] << 4) | (val[1] >> 4)
    temp_c = twos_comp(temp_c, 12)

    # Convert registers value to temperature (C)
    temp_c = temp_c * 0.0625
    pig.i2c_close(handle)
    return temp_c


# Keep track of microseconds elapsed since fall and rise
tick_down = 0


def button_callback(gpio, level, tick):
    """
    Call back for a button push, debounce
    :param gpio: the pin pushed
    :param level: 0-falling 1-rising
    :param tick: millisec from push, wraps at 4294967295
    :return:
    """
    global tick_down
    log.info("Button: {} {} {}".format(gpio,level,tick))

    # Falling button pushed
    if level == 0:
        tick_down = tick

    # Rising button released
    else:
        ticks = tick - tick_down
        log.info("Button ticks:{} {}".format(ticks, tick_down))

        # Roll over if it went over the max tick level
        if ticks < 0:
            ticks = 4294967295 - ticks

        # 8 second push, restart the network
        if ticks > 8000000:

            # Start the network switch process, make sure to kill it if its already running
            # Stop it if it was already running and they hit the button again
            commands = ("sudo systemctl stop network-switch.service",
                        "sudo systemctl start network-switch.service")
            for command in commands:
                ok = subprocess.run(command.split(), stderr=subprocess.PIPE)
                if ok.returncode:
                    log.error("Error:{} trying to do:{}".format(ok.stderr, command))

        # .25 second push, toggle the lights
        elif ticks > 250000:
            log.info('Button lights')
            current_state, _ = state.lights
            if not int(current_state):
                lights('on')
            else:
                lights('off')


def buttons():
    """
    Set up the button use a call back
    :return: Never
    """
    log.info('button')
    pig.set_mode(BUTTON_1_CHANNEL, pigpio.INPUT)
    pig.set_pull_up_down(BUTTON_1_CHANNEL, pigpio.PUD_UP)
    pig.callback(BUTTON_1_CHANNEL, pigpio.EITHER_EDGE, button_callback)

    pig.set_mode(BUTTON_2_CHANNEL, pigpio.INPUT)
    pig.set_pull_up_down(BUTTON_2_CHANNEL, pigpio.PUD_UP)
    pig.callback(BUTTON_2_CHANNEL, pigpio.EITHER_EDGE, button_callback)

    while True:
        time.sleep(.1)


def cpu():
    """
    Get the cpu temperature
    """
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            cpu_temp = f.read()
    except Exception as e:
        cpu_temp = 'error'
        log.error("Error:{} reading cpu temperature".format(str(e)))
    else:
        cpu_temp = float(cpu_temp) / 1000
    state.cpu = cpu_temp

    return cpu_temp


def wifi_signal():
    """
    Get the current wifi signal and essig
    """
    command = "iwconfig wlan0"
    ok = subprocess.run(command.split(), stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if ok.returncode:
        log.error("Error:{}  reading iwconfig".format(ok.stderr))
        return {}
    """
    wlan0     IEEE 802.11  ESSID:"NETGEAR59"
          Mode:Managed  Frequency:2.442 GHz  Access Point: 9C:D3:6D:A5:9F:E4
          Bit Rate=72.2 Mb/s   Tx-Power=31 dBm
          Retry short limit:7   RTS thr:off   Fragment thr:off
          Power Management:on
          Link Quality=61/70  Signal level=-49 dBm
          Rx invalid nwid:0  Rx invalid crypt:0  Rx invalid frag:0
          Tx excessive retries:2  Invalid misc:0   Missed beacon:0
    """
    try:
        lines = ok.stdout.split('\r\n')
        essid = lines[0].split("ESSID:")[1]
        signal = lines[5].split('Signal level=')[1].strip()
    except Exception as e:
        log.error("Error:{} parsing iwconfig".format(str(e)))
        return {}
    return dict(signal=signal, essid=essid)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Control sensors on the board')

    parser.add_argument('sensor',
                        choices=['lights',
                                 'pump',
                                 'camera',
                                 'photos',
                                 'water',
                                 'temperature',
                                 'pcb_temp',
                                 'scan',
                                 'restore'
                                 ],
                        help='sensor to affect')

    parser.add_argument('parameter',
                        nargs='*',
                        help="option parameter for lights")

    pargs = parser.parse_args()
    
    if pargs.sensor == 'lights':
        current_state = lights(*pargs.parameter)
        log.info("Current state of lights {}".format(current_state))

    elif pargs.sensor == 'scan':
        print(i2c_scan())

    elif pargs.sensor == 'cpu':
        cpu()

