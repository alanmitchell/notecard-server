"""Holds a class that process and passes sensor readings to a Blues
Wireless Notecard.
"""
import queue
import threading
import time

import serial
import notecard

class Notecard:

    def __init__(self, upload_period):

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

        # Set the mode and other startup parameters on the Notecard
        with serial.Serial("/dev/ttyUSB0", 9600) as port:
            card = notecard.OpenSerial(port)

            req = dict(
                req = 'hub.set',
                productUID = "com.gmail.tabb99:test",
                sn='burton_158', 
                mode="continuous",
                outbound=360,
                inbound=360
            )
            card.Transaction(req)

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
                self.next_upload += self.upload_period * 60.0
                self.upload()
            time.sleep(2)     # check every two seconds

    def upload(self):

        print('uploading...')
        with serial.Serial("/dev/ttyUSB0", 9600) as port:
            card = notecard.OpenSerial(port)

            # Determine whether a time adjustment should be made for the readings.
            # We may be operating on a Pi where the clock is off due to no network
            # connectivity.
            # Note that this code assumes that all the sensor readings were time-stamped
            # by this computer, so all of the readings have a time problem.
            cur_notecard_time = card.Transaction({'req': 'card.time'})['time']
            time_adj = cur_notecard_time - time.time()

            # only adjust time if it is off by more than 5 seconds
            if abs(time_adj) < 5:
                print('no time adjustment')
                time_adj = 0.0

            readings = []
            while not self.q.empty():
                ts, sensor_id, val = self.q.get()
                ts = round(ts + time_adj, 1)    # adjust and round to tenth of secs
                readings.append( (ts, sensor_id, val) )
            
            # TO DO: should implement some compression here
            req = dict(
                req = 'note.add',
                body = {'readings': readings}
            )
            resp = card.Transaction(req)
            print(resp)
            card.Transaction({'req': 'hub.sync'})
