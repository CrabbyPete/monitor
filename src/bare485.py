#!/usr/bin/env python3

import logging
import minimalmodbus
import RPi.GPIO as GPIO

import serial
import serial.rs485

TXDEN = 17 # Transmit enable pin

GPIO.setmode(GPIO.BCM)
GPIO.setup(TXDEN, GPIO.OUT)
GPIO.output(TXDEN, GPIO.HIGH)

logging.basicConfig()
log = logging.getLogger("modbus")
log.setLevel(logging.DEBUG)


# These are barebones register writes for testing
commands = [bytearray([0x1, 0x6, 0x80, 0x0, 0x9, 0x2, 0x27, 0x9b]), # Start
            bytearray([0x1, 0x6, 0x80, 0x5, 0xe8, 0x3, 0xbe, 0xa]), # Set speed 1000
            bytearray([0x1, 0x6, 0x80, 0x0, 0xa, 0x2, 0x27, 0x6b])  # Stop
            ]

# This function just writes simple commands
def write_485(port):
    s=serial.rs485.RS485(port, baudrate=9600, parity=serial.PARITY_NONE)
    s.rs485_mode = serial.rs485.RS485Settings(False,True)
    for command in commands:
        GPIO.output(TXDEN, GPIO.HIGH)
        s.write(command)
        log.info(f'Wrote {command} to BLD-510')
        s.flush()
        GPIO.output(TXDEN, GPIO.LOW)
        if s.in_waiting:
            to_read = s.in_waiting
            data = s.read(s.in_waiting)
            log.info(f"Recieved:{to_read}, {data}")


class MyRS485(serial.rs485.RS485):
    """
    Use this with minimalmod bus to enable the writes to the Max485 chip
    """
    def setRTS(self, value):
        GPIO.output(TXDEN, GPIO.LOW if value else GPIO.HIGH)


class Modbus():
    def __init__(self, port='/dev/ttyS0'):
        s = MyRS485(port, baudrate=9600, parity=serial.PARITY_NONE)
        s.rs485_mode = serial.rs485.RS485Settings(False, True)
        self.instrument = minimalmodbus.Instrument(s, 1)

    def start(self):
        """
        Start. The actual motor has 4 poles
        :return:
        """
        try:
            self.instrument.write_register(0x8000, 0x0902, functioncode=6)
        except:
            return False
        return True

    def stop(self):
        try:
            self.instrument.write_register(0x8000, 0x0a02, functioncode=6)
        except:
            return False
        return True

    def reverse(self):
        try:
            self.instrument.write_register(0x8000, 0x0B02, functioncode=6)
        except:
            return False
        return True

    def speed(self, speed):
        try:
            new_value = speed.to_bytes(2,'little')
            self.instrument.write_register(0x8005, int.from_bytes(new_value,'big'), functioncode=6)
        except:
            return False
        return True

    def get_speed(self):
        value = self.instrument.read_register(0x8005)
        return int.from_bytes(value.to_bytes(2,'little'), 'big')

    def get_alarms(self):
        current = self.instrument.read_register(0x8004)
        value = self.instrument.read_register(0x801B)
        return hex(value)

    def __enter__(self):
        pass

    def __exit__(self, ext, exv, trb):
        self.instrument.close()

if __name__ == "__main__":

    m = Modbus()
    m.start()
    m.speed(1000)
    m.reverse()
    print(f"Speed:{m.get_speed()}")
    print(f"Alarms:{m.get_alarms()}")
    m.stop()
    #write_485('/dev/ttyS0')
    # '/dev/cu.usbserial-B000Z1J0' # on a Mac