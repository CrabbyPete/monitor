import os
import redis
import arrow

from dataclasses import dataclass

from log import log

@dataclass
class SystemState:
    """
    Keep track of the system status in redis
    """
    def __init__(self, system_id=None):
        """
        Initial the system status with Redis
        :param system_id: system id number
        """
        self.redis = redis.Redis(decode_responses=True)
        fp = os.popen("cat /proc/cpuinfo | grep Serial | cut -d ' ' -f 2 | md5sum | cut -d ' ' -f 1")
        self.redis.set('serial',fp.read().splitlines()[0])

        if not self.redis.get('version'):
            self.redis.set('version','1.0')

        if not self.redis.get('timezone'):
            self.redis.set('timezone', 'America/New_York')

        self.lights = 0
        self.red_led = 0
        self.ir_led = 0
        self.microphone = 0
        self.speakers = 0
        self.camera = 0
        self.motor = [0,0]

    @property
    def timezone(self):
        return self.redis.get('timezone')

    @property
    def serial(self):
        try:
            return self.redis.get('serial')
        except:
            return None


    def config(self, device, **kwargs):
        """
        Get and set configuration of a device
        :param device: str: which device to configure or get
        :param kwargs: dict: change values to set eg. duty_cycle:100, frequency: 2000
        :return: dict: current settings
        """
        settings = self.redis.hget('config',device)
        configuration = json.loads(settings)
        if kwargs:
            for k,v in kwargs:
                parameter = configuration.get(k)
                if parameter:
                    configuration[k] = v
            self.redis.hset('config',device,json.dumps(configuration))
        return configuration

    @property
    def version(self):
        return self.redis.get('version')

    @property
    def lights(self):
        state = self.redis.hget('lights','state')
        time = self.redis.hget('lights','time')
        return state, time

    @lights.setter
    def lights(self, state):
        self.redis.hset('lights', 'state', state)
        self.redis.hset('lights', 'time', arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def red_led(self):
        state = self.redis.hget('red_led','state')
        time = self.redis.hget('red_led','time')
        return state, time

    @red_led.setter
    def red_led(self, state):
        self.redis.hset('red_led', 'state', state)
        self.redis.hset('red_led', 'time', arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def ir_led(self):
        state = self.redis.hget('ir_led','state')
        time = self.redis.hget('ir_led','time')
        return state, time

    @ir_led.setter
    def ir_led(self, state):
        self.redis.hset('ir_led', 'state', state)
        self.redis.hset('ir_led', 'time', arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def camera(self):
        return self.redis.hget('camera','path'), self.redis.hget('camera','time')

    @camera.setter
    def camera(self, path):
        self.redis.hset('camera_one','path',path)
        self.redis.hset('camera_one','time',arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def temperature(self):
        t = self.redis.hget('temperature','temperature')
        return t, self.redis.hget('temperature','time')

    @temperature.setter
    def temperature(self, value):
        self.redis.hset('temperature','temperature', value)
        self.redis.hset('temperature','time', arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def motor(self):
        return self.redis.hget('motor','state'), self.redis.hget('motor','speed')

    @motor.setter
    def motor(self, values):
        self.redis.hset('motor', 'state', values[0])
        self.redis.hset('motor', 'speed', values[1])
        self.redis.hset('motor', 'time', arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def cpu(self):
        return self.redis.hget('cpu', 'temperature'), self.redis.hget('cpu', 'time')

    @cpu.setter
    def cpu(self, temperature):
        self.redis.hset('cpu','temperature', temperature)
        self.redis.hset('cpu','time',arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def connected(self):
        return int(self.redis.get('connected'))

    @connected.setter
    def connected(self, is_connected):
        self.redis.set('connected', 1 if is_connected else 0)

    @property
    def connection(self):
        try:
            return self.redis.get('connection')
        except:
            return None

    @connection.setter
    def connection(self, string):
        self.redis.set('connection',string)

    @property
    def network(self):
        return(self.redis.hget('network','ssid'), self.redis.hget('network','password'))

    @network.setter
    def network(self, value):
        self.redis.hset('network','ssid', value[0])
        self.redis.hset('netowrk','password', value[1])

    @property
    def device_id(self):
        try:
            return self.redis.get('device_id')
        except:
            return None

    @device_id.setter
    def device_id(self, string):
        self.redis.set('device_id',string)


    def __repr__(self):
        status = {
            "temp": self.temperature[0],
            "light": self.lights[0],
            "prev_light": 1,
            "network":self.network,
            "serial":self.serial,
            "version":self.version,
            "timezone":self.timezone
        }
        return json.dumps(status)


state = SystemState()


if __name__ == "__main__":
    import json
    print(state)


