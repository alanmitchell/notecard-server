"""Holds a class that process and passes sensor readings to a Blues
Wireless Notecard.
"""
import queue
import threading
import time

import serial
import notecard
from notecard import hub

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

        # create a Notecard object using the company Notecard library
        # Use pySerial on a PC or SBC
        port = serial.Serial("/dev/ttyUSB0", 9600)
        self.nCard = notecard.OpenSerial(port)

        productUID = "com.analysisnorth:sensor"
        rsp = hub.set(self.nCard, productUID, mode="continuous")
        print(rsp)

    def add_sensor_reading(self, ts, sensor_id, val):
        """Adds a sensor reading to the Queue that will get uploaded via the Notecard.
        """
        # TO DO: Adjust time here if Notecard time is more than 5 seconds different
        # than computer time. This assumes these readings originated on this computer.
        pass

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

        while not self.q.empty():
            rec = self.q.get()
            print(f'uploading {rec}')
