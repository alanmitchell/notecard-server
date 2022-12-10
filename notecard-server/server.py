import json

from bottle import run, request, post

import blues

nCard = blues.Notecard(
    0.5, 
    '/dev/ttyUSB0',
    "com.gmail.tabb99:test",
    'Okla511'
    )

@post('/minimon')
def mini_data():
    payload = json.loads(request.body.read())
    for ts, sensor_id, val in payload['readings']:
        nCard.add_sensor_reading(ts, sensor_id, val)
    return f"{len(payload['readings'])}\n"

run(host='localhost', port=5000, debug=True)
