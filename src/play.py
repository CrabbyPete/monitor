import sys
from sensorctl import speakers

if __name__ == "__main__":

    while True:
        speakers('play',sys.argv)

