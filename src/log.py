import os
import sys
import logging
import inspect


log = logging.getLogger('crib')
log.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
log_format = logging.Formatter('[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s','%m-%d %H:%M:%S')
handler.setFormatter(log_format)
log.addHandler(handler)


def log_detail( msg ):
    stack = inspect.stack()[1]
    file = os.path.basename( stack[1] )
    msg =  'Error: {} @ {}:{}'.format (msg, file, stack[2] )
    print(msg)
    return msg

if __name__ == "__main__":
    pass