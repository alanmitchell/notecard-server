from bottle import run, request, post

import blues

nCard = blues.Notecard(0.5)

@post('/minimon')
def mini_data():
    payload = request.json
    for ts, sensor_id, val in payload['readings']:
        nCard.add_sensor_reading(ts, sensor_id, val)
    return f"{len(payload['readings'])}\n"

run(host='localhost', port=5000, debug=True)
