import json
import sys
from pathlib import Path
from importlib import import_module

from bottle import run, request, post

import blues

# First command line argument is required and must give a path to a settings file.
# Path to config file
config_file = Path(sys.argv[1])
config_dir = str(config_file.parent)
if config_dir != '.':
    sys.path.insert(0, config_dir)
settings = import_module(config_file.stem)

# determine parameters for Notecard constructor
param = {
    'product_uid': settings.NOTECARD_PRODUCT,
    'sn_string': settings.NOTECARD_SN_STRING
}
if hasattr(settings ,'NOTECARD_PORT_NAME'):
    param['port_name'] = settings.NOTECARD_PORT_NAME
if hasattr(settings, 'NOTECARD_UPLOAD_PERIOD'):
    param['upload_period'] = settings.NOTECARD_UPLOAD_PERIOD

nCard = blues.Notecard(**param)

@post('/minimon')
def mini_data():
    payload = json.loads(request.body.read())
    for ts, sensor_id, val in payload['readings']:
        nCard.add_sensor_reading(ts, sensor_id, val)
    return f"{len(payload['readings'])}\n"

run(host='localhost', port=5000, debug=False)
