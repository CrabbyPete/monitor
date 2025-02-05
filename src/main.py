import time

import sensorctl

from threading  import Thread

from log        import log
from status     import state


class Button(Thread):
    """
    Watch and handle the button
    :return:
    """
    def run(self):
        log.info("Starting button")
        try:
            sensorctl.buttons()
        except Exception as e:
            log.error("Error {} on button".format(str(e)))


def main():
    """
    Main loop which starts multiple threads
    :return:
    """
    sensorctl.lights('blink', 3)
    log.info(f"Current temperature:{sensorctl.temperature()}")

    # Start each of the threads that monitor button, water, and schedule
    button = Button()
    button.start()

    jobs = [button]
    while True:

        # Check each job in the case it stops for some reason, and if not restart it
        for jn, job in enumerate(jobs):
            try:
                job.join(0)
            except Exception as e:
                log.error(f"Error:{e} trying to join job #{jn}")

            # If a job is dead, create a new one and restart it
            if not job.is_alive():
                if jn == 0:
                    log.info("Restarting Button")
                    jobs[jn] = Button()

                jobs[jn].start()
                break
        time.sleep(5)


if __name__ == '__main__':
    log.info("MAIN IOT STARTING")
    main()
