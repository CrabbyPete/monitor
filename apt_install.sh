set -x
apt update -y
apt upgrade -y

raspi-config nonint do_i2c 1
raspi-config nonint do_serial 1

apt install -y python3-pip
apt install -y pigpiod python3-pigpio
apt install -y redis
apt install -y i2c-tools
apt install -y emacs-nox

systemctl enable pigpiod
systemctl start pigpiod
