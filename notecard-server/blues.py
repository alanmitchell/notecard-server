"""Holds a class that process and passes sensor readings to a Blues
Wireless Notecard.
"""
import queue
import threading
import time
import base64
import bz2
import datetime
import subprocess

import serial
from periphery import I2C
import notecard


class Notecard:

    def __init__(self, 
        product_uid, 
        sn_string,
        port_name='/dev/i2c-1',
        upload_period=60.0,
        set_time=True,
        ):
        """product_uid:  The Product UID on Note Hub where the data should go.
        sn_string:  the serial number string that identifies this Notecard, you create it.
        port_name:   e.g. '/dev/ttyUSB0' or '/dev/i2c-1'
        upload_period:  amount of time in minutes between uploads to Note Hub.
            Readings are batched in between uploads.
        set_time: if True, used the time on the Notecard to set the computer time after
            Notecard uploads if it differs noticeably from Notecard time.
        """

        self.port_name = port_name
        self.set_time = set_time

        # Set the mode and other startup parameters on the Notecard
        while True:
            try:
                card = self.open_card()

                # set to factory defaults
                req = dict(
                    req = 'card.restore',
                    delete = True
                )
                card.Transaction(req)

                # set necessary configuration
                req = dict(
                    req = 'hub.set',
                    product = product_uid,
                    sn=sn_string, 
                    mode="continuous",
                    outbound=720,
                    inbound=720
                )
                card.Transaction(req)
                card.Transaction({'req': 'hub.sync'})
                break

            except Exception as e:
                print("Couldn't complete Notecard setup. Retrying...", e)
                # try again
                time.sleep(3)

        # The time between requesting a Notecard sync to upload sensor readings.
        # The units are minutes.
        self.upload_period = upload_period
        self.next_upload = time.time() + upload_period * 60.0

        # the FIFO queue that holds sensor readings prior to being 
        # delivered to the Notecard
        self.q = queue.Queue()

        # Start the function that checks to see if it is time to upload readings
        # via the notecard.
        threading.Thread(target=self.upload_timer, daemon=True).start()

    def open_card(self):
        """Creates a notecard object using communication on the port identified
        on self.port_name.  Retries until a connection is made.  Returns the 
        card object.
        I have seen the card fail to open when it is sleeping; the retry has
        been successful, though.  So, the retry is important.
        """
        is_i2c = 'i2c' in self.port_name

        # keep trying to connect
        while True:
            try:
                if is_i2c:
                    port = I2C(self.port_name)
                    return notecard.OpenI2C(port, 0, 0)

                else:
                    port = serial.Serial(self.port_name, 9600)
                    return notecard.OpenSerial(port)

            except Exception as e:
                print("Couldn't open Notecard port. Trying again...", e)
                # go back and try again.
                time.sleep(3)

    def add_sensor_reading(self, ts, sensor_id, val):
        """Adds a sensor reading to the Queue that will get uploaded via the Notecard.
        """
        # add this sensor readings to the queue
        self.q.put( (ts, sensor_id, val) )

    def upload_timer(self):
        """Runs in a separate thread and triggers an upload once self.upload_period
        expires, if there are sensor readings to upload.
        """
        while True:
            if time.time() >= self.next_upload and not self.q.empty():
                while True:
                    try:
                        self.upload()
                        self.next_upload = time.time() + self.upload_period * 60.0
                        break

                    except Exception as e:
                        print('Error uploading readings. Trying again...', e)
                        time.sleep(3)

            time.sleep(2)     # check every two seconds

    def upload(self):
        """Create a Note containting all the queued readings and uploads to the
        Note Hub.
        Calling routine is responsible for handling errors.
        """
        card = self.open_card()

        # Determine whether a time adjustment should be made for the readings.
        # We may be operating on a Pi where the clock is off due to no network
        # connectivity.
        # Note that this code assumes that all the sensor readings were time-stamped
        # by this computer, so all of the readings have a time problem.
        time_adj = 0.0
        resp = card.Transaction({'req': 'card.time'})
        if 'time' in resp:
            cur_notecard_time = resp['time']
            time_adj = cur_notecard_time - time.time()

            # only adjust time if it is off by more than 10 seconds
            if abs(time_adj) < 10:
                time_adj = 0.0
            else:
                # if requested also correct computer time
                if self.set_time:
                    new_dt = datetime.datetime.utcfromtimestamp(cur_notecard_time).strftime('%Y-%m-%d %H:%M:%S')
                    subprocess.run([f'sudo date -u -s "{new_dt}"'], shell=True)
                    print(f'Set computer time to {new_dt} UTC.')


        print(f'Uploading.  Time offset {time_adj:.1f} seconds.')

        readings = []
        while not self.q.empty():
            ts, sensor_id, val = self.q.get()
            ts = round(ts + time_adj, 1)    # adjust and round to tenth of secs
            readings.append( (ts, sensor_id, val) )

        # Compress the new readings array by converting to a string, implementing
        # bz2 compression and then convert to a base64 string.
        reads_compressed = bz2.compress(str(readings).encode('utf-8'))
        reads_b64 = base64.b64encode(reads_compressed).decode('utf-8')

        req = dict(
            req = 'note.add',
            body = {
                'reading_type': 'ts_id_val_bz2',
                'readings': reads_b64,
                }
        )
        resp = card.Transaction(req)
        print(resp)
        card.Transaction({'req': 'hub.sync'})
