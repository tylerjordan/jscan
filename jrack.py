# Author: Tyler Jordan
# File: jrack.py
# Last Modified: 4/21/2016
# Description: Classes for a Juniper device container and Juniper devices.

import datetime

from datetime import datetime
from pprint import pprint

class JRack:
	
	def __init__(self):
		'''Initialize a rack without any devices.'''
		self.devices = []
	
	def new_device(self, ip, model, code, hostname):
		'''Add a new device to the rack.'''
		self.devices.append(JDevice(ip, model, code, hostname))


class JDevice:
	
	def __init__(self, ip, model, code, hostname):
		''' Initialize all elements of device.'''
		self.hostname = hostname
		self.ip = ip
		self.model = model
		self.code = code
		self.refresh = datetime.now() 
		self.active = True
	
	def refresh(self):
		''' Resets the value after a successful scan.''' 
		pass