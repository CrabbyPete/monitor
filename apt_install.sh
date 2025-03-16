set -x
apt update -y
apt upgrade -y

raspi-config nonint do_i2c 1
raspi-config nonint do_serial 1

apt install -y python3-pip python3-venv
apt install -y git emacs-nox redis i2c-tools
apt install -y python3-rpi-lgpio python3-arrow python3-redis python3-pymodbus
apt install -y libgstreamer1.0-dev \
  gstreamer1.0-alsa \
  libgstreamer-plugins-base1.0-dev \
  libgstreamer-plugins-bad1.0-dev \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav \
  gstreamer1.0-tools \
  gstreamer1.0-libcamera

pip3 install --break-system-packages smbus2

# python3-gst-1.0