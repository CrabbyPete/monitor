#!/usr/bin/env python3
import os
import time
import arrow
import pigpio
import subprocess

# Local imports
from log        import log
from status     import state

MIN_DUTY = 0
MAX_DUTY = 255

PUMP_CHANNEL = 24
PUMP_FREQ = 10000
PUMP_DUTY = 126         # Percentage of 256 126 ~= 50%

BUTTON_1_CHANNEL = 27
BUTTON_2_CHANNEL = 22

LED_CHANNEL = 12        # PWM LED channel
LED_FREQUENCY = 10000

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


def red_led(command):
    """
    Turn on and off red light
    :param command: str 'on'|'off
    :return:
    """
    value = 1 if command == 'on' else 0
    pig.write(RED_LED_CHANNEL, value)
    state.red_led = value


def ir_led(command):
    """
    Turn on and off IR LED
    :param command: str: 'on'|'off
    :return:
    """
    value = 1 if command == 'on' else 0
    pig.write(IR_LED_CHANNEL, value)
    state.ir_led = value


def lights(command, *values):
    """
    Turn on and off the leds
    :param command: str: on, off, boost, or integer value
    :param values: option value for a given command
    :return:
    """
    log.info(f"lights {command} {values}")
    pig.set_PWM_frequency(LED_CHANNEL, LED_FREQUENCY)

    # Current state has to be a percentage of the maximum duty cycle 255.
    if values:
        if isinstance(values[0], str):
            try:
                value = int(values[0])
            except TypeError:
                value = 1
        else:
            value = int(values[0])

    if command == 'on':
        duty_cycle = int(MAX_DUTY/2)

    elif command == 'boost':
        duty_cycle = MAX_DUTY

    elif command == 'off':
        duty_cycle = 0

    elif command == 'adjust':
        # Adjust the current value by percent of current value # Note the app is sending this after an 'off'
        current, _ = state.lights
        current = int(current) + values[0]
        current = min(max(current,0),100)
        duty_cycle = int( MAX_DUTY * ( current / 100 ))

    elif command == 'set':
        value = min(max(values[0],0),100)
        duty_cycle = int( MAX_DUTY * ( value / 100 ))

    elif command == 'blink':
        # Blink the lights value times
        current_state = int(state.lights[0])

        for _ in range(value):
            pig.set_PWM_dutycycle(LED_CHANNEL,MAX_DUTY)
            time.sleep(1)

            pig.set_PWM_dutycycle(LED_CHANNEL, MIN_DUTY)
            time.sleep(1)

        duty_cycle = current_state

    pig.set_PWM_dutycycle(LED_CHANNEL, duty_cycle)
    state.lights = duty_cycle

    return duty_cycle

def play(command, *values):
    """
    Ploy or stop sound from the speakers
    :param command:
    :param values:
    :return:
    """

def microphone(command):
    """
    Turn on and off the microphone
    :param command:
    :return:
    """
    # Send audio output to process or socket
    if command == 'on':
        command = "arecord -D plughw:1 -c1 -r 48000 -f S32_LE -t wav -V mono -v file.wav"
        ok = subprocess.run(command.split(), stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    else:
        pass


def motor(command):
    """
    Get the current water level
    :return:
    """
    # log.info("Reading water level")
    if command == 'on':
        state.motor = 1
    else:
        state.motor = 0


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


def temperature(bus=1, address=0x48):
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
    pig.i2c_write_i2c_block_data(handle, 0x01, data)

    _, val = pig.i2c_read_i2c_block_data(handle,0x00,2)
    temp_c = (val[0] << 4) | (val[1] >> 4)
    temp_c = twos_comp(temp_c, 12)

    # Convert registers value to temperature (C)
    temp_c = temp_c * 0.0625
    pig.i2c_close(handle)
    state.temperature = temp_c
    return temp_c


# Keep track of microseconds elapsed since fall and rise
tick_down=[0,0]


def button_callback(gpio, level, tick):
    """
    Call back for a button push, debounce
    :param gpio: the pin pushed
    :param level: 0-falling 1-rising
    :param tick: millisec from push, wraps at 4294967295
    :return:
    """
    global tick_down
    button = 0 if gpio == BUTTON_1_CHANNEL else 1

    log.info("Button: {} {} {}".format(gpio,level,tick))

    # Falling button pushed
    if level == 0:
        tick_down[button] = tick

    # Rising button released
    else:
        ticks = tick - tick_down[button]
        log.info("Button ticks:{} {}".format(ticks, tick_down[button]))

        # Roll over if it went over the max tick level
        if ticks < 0:
            ticks = 4294967295 - ticks

        # .25 second push, toggle the lights
        elif ticks > 250000:
            if button == 0:
                log.info('Button lights')
                current_state, _ = state.lights
                if not int(current_state):
                    lights('on')
                else:
                    lights('off')
            else:
                log.info('IR button')
                current_state, _ = state.red_led
                if not int(current_state):
                    red_led('on')
                    ir_led('on')
                else:
                    red_led('off')
                    ir_led('off')


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
                                 'red_led',
                                 'ir_led',
                                 'temperature',
                                 'scan',
                                 'buttons'
                                 ],
                        help='sensor to affect')

    parser.add_argument('parameter',
                        nargs='*',
                        help="option parameter for lights")

    pargs = parser.parse_args()
    if pargs.sensor == 'temperature':
        temp_c = temperature()
        temp_f = (temp_c * 1.8) + 32
        print(f"Celcius:{temp_c} Fahrenheit:{temp_f}")

    elif pargs.sensor == 'red_led':
        red_led(*pargs.parameter)

    elif pargs.sensor == 'ir_led':
        ir_led(*pargs.parameter)
    
    elif pargs.sensor == 'lights':
        current_state = lights(*pargs.parameter)
        log.info("Current state of lights {}".format(current_state))

    elif pargs.sensor == 'scan':
        print(i2c_scan())

    elif pargs.sensor == 'cpu':
        cpu()

    else:
        buttons()

