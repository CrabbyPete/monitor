import time
from threading import Thread

import sensorctl
from log import log


class Button(Thread):
    """
    Watch and handle the button
    :return:
    """
    def run(self):
        log.info("Starting button")
        try:
            sensorctl.button()
        except Exception as e:
            log.error("Error {} on button".format(str(e)))


if __name__ == "__main__":
    while True:
        sensorctl.buttons()
