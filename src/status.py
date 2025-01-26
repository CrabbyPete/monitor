import os
import json
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
            self.redis.set('version','2.0')

        if not self.redis.get('timezone'):
            self.redis.set('timezone', 'America/New_York')

    @property
    def timezone(self):
        return self.redis.get('timezone')

    @property
    def serial(self):
        try:
            return self.redis.get('serial')
        except:
            return None

    def schedule(self, device, **kwargs):
        """
        Scheduled settings in the systemd timers for each device
        :param device: str: defined by they systemd.timer eg. lights_on, lights_boost, lights_off, pump, camera
        :param kwargs: list[str]: list of string defining the schedule as a system.timer value eg.['*-*-* 10:00:00']
        :return:
        """
        settings = self.redis.hget('schedule',device)
        configuration = json.loads(settings)
        if kwargs:
            for k,v in kwargs:
                pass

        return configuration

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
    def pump(self):
        return self.redis.hget('pump','state'), self.redis.hget('pump','time')

    @pump.setter
    def pump(self, value):
        self.redis.hset('pump', 'state', value)
        self.redis.hset('pump', 'time', arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def power(self):
        return self.redis.hget('power','state'), self.redis.hget('power','time')

    @power.setter
    def power(self, value):
        self.redis.hset('power', 'state', value)
        self.redis.hset('power', 'time', arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def camera_one(self):
        return self.redis.hget('camera_one','path'), self.redis.hget('camera_one','time')

    @camera_one.setter
    def camera_one(self, path):
        self.redis.hset('camera_one','path',path)
        self.redis.hset('camera_one','time',arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def camera_two(self):
        return self.redis.hget('camera_one','path'), self.redis.hget('camera_one','time')

    @camera_two.setter
    def camera_two(self, path):
        self.redis.hset('camera_two','path',path)
        self.redis.hset('camera_two','time',arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def water(self):
        return self.redis.hget('water','level'), self.redis.hget('water','time')

    @water.setter
    def water(self, level):
        self.redis.hset('water','level', level)
        self.redis.hset('water','time', arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def temperature(self):
        t = self.redis.hget('temperature','temperature')
        h = self.redis.hget('temperature','humidity')
        return t,h,self.redis.hget('temperature','time')

    @temperature.setter
    def temperature(self, values):
        self.redis.hset('temperature','temperature', values[0])
        self.redis.hset('temperature','humidity', values[1])
        self.redis.hset('temperature','time',arrow.now().format("YYYYMMDD HH:mm:ss"))

    @property
    def pcb_temp(self):
        return self.redis.hget('pcb_temp', 'temperature'), self.redis.hget('pcb_temp','time')

    @pcb_temp.setter
    def pcb_temp(self, temperature):
        self.redis.hset('pcb_temp','temperature', temperature)
        self.redis.hset('pcb_temp','time',arrow.now().format("YYYYMMDD HH:mm:ss"))

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
    def network(self, ssid, password):
        self.redis.hset('network','ssid', ssid)
        self.redis.hset('netowrk','password', password)

    @property
    def camera(self):
        return self.redis.get('camera')

    @camera.setter
    def camera(self,value=arrow.now().format('YYYYMMDD_HHmm')):
        self.redis.set('camera', value)

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
            "humidity": self.temperature[1],
            "water_lvl": self.water[0],
            "light": self.lights[0],
            "pump": self.pump[0],
            "light_schedule": 1,
            "pump_schedule": 1,
            "prev_light": 1,
            "camera_status": 1,
            "power": self.power[0],
            "board": self.pcb_temp[0],
            "version":self.version,
            "timezone":self.timezone
        }
        return json.dumps(status)


state = SystemState()

if __name__ == "__main__":
    print(state)


