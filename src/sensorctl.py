#!/usr/bin/env python3
import os
import time
import smbus2
import subprocess
import RPi.GPIO as GPIO

from pymodbus.client import ModbusSerialClient

# Local imports
from log        import log
from status     import state

MIN_DUTY = 0
MAX_DUTY = 100
MOTOR_CHANNEL = '/dev/ttyUSB0'

BUTTON_1_CHANNEL = 27
BUTTON_2_CHANNEL = 22

LED_CHANNEL = 12        # PWM LED channel
LED_FREQUENCY = 10000
IR_LED_CHANNEL = 6
RED_LED_CHANNEL = 13
HOME = os.path.dirname(os.path.realpath(__file__))

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(LED_CHANNEL, GPIO.OUT )
GPIO.setup(IR_LED_CHANNEL, GPIO.OUT )
GPIO.setup(RED_LED_CHANNEL, GPIO.OUT)


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
    GPIO.output(RED_LED_CHANNEL, value)
    state.red_led = value


def ir_led(command):
    """
    Turn on and off IR LED
    :param command: str: 'on'|'off
    :return:
    """
    value = 1 if command == 'on' else 0
    GPIO.output(IR_LED_CHANNEL, value)
    state.ir_led = value

pwm = GPIO.PWM(LED_CHANNEL, LED_FREQUENCY)
pwm.start(0)

def lights(command, *values):
    """
    Turn on and off the leds
    :param command: str: on, off, boost, or integer value
    :param values: option value for a given command
    :return:
    """
    log.info(f"lights {command} {values}")

    # Current state has to be a percentage of the maximum duty cycle 255.
    if values:
        if isinstance(values[0], str):
            try:
                value = int(values[0])
            except TypeError:
                log.error(f"Type error in lights for {values}")
        else:
            value = int(values[0])

    if command == 'on':
        duty_cycle = 50

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
            pwm.ChangeDutyCycle(100)
            time.sleep(1)

            pwm.ChangeDutyCycle(0)
            time.sleep(1)

        duty_cycle = current_state

    print(f"duty_cycle:{duty_cycle}")
    pwm.ChangeDutyCycle(duty_cycle)
    state.lights = duty_cycle

    return duty_cycle


def speakers(command, *values):
    """
    Ploy or stop sound from the speakers
    :param command: 'play' or 'stop
    :param values: str: name of file to play
    :return:
    """
    if command == 'play':
        value = values[0]
        if not value:
            value = os.path.join(HOME,'lullaby.wav')

        command = f"aplay {value}"
        ok = subprocess.run(command.split(), stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        if ok:
            if ok.returncode:
                print(ok.stderr)


def microphone(command):
    """
    Turn on and off the microphone
    :param command:
    :return:
    """
    # Send audio output to process or socket
    if command == 'on':
        command = "arecord -D plughw:0 -c1 -r 48000 -f S32_LE -t wav -V mono -v file.wav"
        ok = subprocess.run(command.split(), stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    else:
        pass

def record(command,*options):
    """
    Manage recording
    :param command: str: on or off
    :param options: n
    :return:
    """
    pass


def motor(command, *speed):
    """
    Get the current water level
    :return:
    """
    try:
        client = ModbusSerialClient(MOTOR_CHANNEL,
                                    baudrate= 9600,
                                    bytesize=8,
                                    parity="N",
                                    stopbits=1)
        client.connect()
    except Exception as e:
        log.error(f"Error:{e} trying to connect to motor")
        return

    if command == 'on':
        ok = client.write_register(0x8000,0x0902)
        if speed[0]:
            ok =  client.write_register(0x8005, speed)
    elif command == 'off':
        ok = client.write_register(0x8000,0x0A02)
    elif command == 'reverse':
        ok = client.write_register(0x8000,0x0B02)
    client.close()


def i2c_scan(bus_number=1):
    """Scans the I2C bus for devices."""
    bus_addresses = []
    with smbus2.SMBus(bus_number) as bus:
        for address in range(0x08, 0x79):
            try:
                bus.read_byte(address)
                bus_addresses.append(address)
            except Exception:
                pass
    return bus_addresses


def temperature(bus=1, address=0x49):
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

    with smbus2.SMBus(1) as bus:

        # Read the configuration block
        data = bus.read_i2c_block_data(address, 0x01, 2)

        # Set to 4 Hz sampling (CR1, CR0 = 0b10)
        data[1] = data[1] & 0b00111111
        data[1] = data[1] | (0b10 << 6)

        # Write 4 Hz sampling back to CONFIG
        bus.write_i2c_block_data(address, 0x01, data)

        val = bus.read_i2c_block_data(address, 0x00, 2)
        temp_c = (val[0] << 4) | (val[1] >> 4)
        temp_c = twos_comp(temp_c, 12)

    # Convert registers value to temperature (C)
    temp_c = temp_c * 0.0625
    state.temperature = temp_c
    return temp_c


# Keep track of microseconds elapsed since fall and rise
tick_down=[0,0]

def button_callback(channel):
    global tick_down

    up = GPIO.input(channel)
    print(channel, up)

    # Keep track of the time for each button
    tick:int =  0 if channel == BUTTON_1_CHANNEL else 1

    # If the button is down, record starting time until it comes up
    if not up:
        print('d')
        tick_down[tick] = time.time()
    else:
        print('u')
        hold = time.time() - tick_down[tick]
        if channel == BUTTON_1_CHANNEL:
            if hold > 1.:
                if not int(state.lights[0]):
                    lights('on')
                else:
                    lights('off')
        else:
            print("play")
            pass



def buttons():
    """
    Set up the buttons. Make sure the process that calls this waits forever
    :return: None
    """
    GPIO.setup(BUTTON_1_CHANNEL, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BUTTON_2_CHANNEL, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    try:
        GPIO.add_event_detect(BUTTON_1_CHANNEL, GPIO.BOTH, callback=button_callback, bouncetime=500)
    except Exception as e:
        log.error(f"Error:{e} on {BUTTON_1_CHANNEL}")
    try:
        GPIO.add_event_detect(BUTTON_2_CHANNEL, GPIO.BOTH, callback=button_callback, bouncetime=500)
    except Exception as e:
        log.error(f"Error:{e} on {BUTTON_2_CHANNEL}")



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
                                 'speakers',
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
        lights(*pargs.parameter)
        log.info("Current state of lights {}".format(state.lights))

    elif pargs.sensor == 'speakers':
        speakers('play',os.path.join(HOME,'lullaby.wav'))

    elif pargs.sensor == 'microphone':
        microphone('on')

    elif pargs.sensor == 'scan':
        print(i2c_scan())

    elif pargs.sensor == 'cpu':
        cpu()

    else:
        buttons()
