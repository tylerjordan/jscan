# Author: Tyler Jordan
# File: jrack.py
# Last Modified: 7/28/2016
# Description: Classes for a Juniper device container and Juniper devices.

import datetime


class JRack:

    def __init__(self):
        # Initialize a rack without any devices
        self.devices = []

    def new_device(self, ip, model, curr_code, tar_code, hostname):
        # Add a new device to the rack
        self.devices.append(JDevice(ip, model, curr_code, tar_code, hostname))

    def __del__(self):
        # Removes JRack
        pass


class JDevice:

    def __init__(self, ip, model, curr_code, tar_code, hostname):
        # Initialize all elements of device
        self.hostname = hostname
        self.ip = ip
        self.model = model
        self.curr_code = curr_code
        self.tar_code = tar_code
        self.refresh = datetime.datetime.now()
        self.active = True

    def refresh(self):
        # Resets the value after a successful scan
        pass

    def upgrade(self, code_dest):
        # Upgrade a device
        pass

    def __del__(self):
        # Removes the devices
        pass