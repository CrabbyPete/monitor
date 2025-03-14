import json

import sensorctl
from status import state


def lights(value):
    """
    Turn off the lights
    :param payload: ignored
    :return:
    """
    sensorctl.lights(value)
    return state.lights


def red_led(value):
    """
    Turn off the lights
    :param payload: ignored
    :return:
    """
    parm = 'on' if value else 'off'
    sensorctl.red_led(parm)
    return state.red_led


def ir_led(value):
    """
    Turn on the ir_led
    :param value: 'on' or 'off'
    :return:
    """
    sensorctl.ir_led(value)
    return state.ir_led


def microphone(values):
    return state.microphone


def video(values):
    return state.video

def motor(values):
    return state.motor

def button_one(value):
    pass

def button_two(value):
    pass

def temperature(value):
    pass

def speakers(value):
    pass

