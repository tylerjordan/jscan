# Author: Tyler Jordan
# File: jscan.py
# Last Modified: 5/2/2016
# Description: main execution file, starts the top-level menu

import os, sys
import utility

from jnpr.junos import Device
from jrack import JRack, JDevice
from utility import *

class Menu:
	username = "tjordan"
	password = "ah64dlb"
	list_dir = ".\\lists\\"
	
	'''Display a menu and respond to choices when run.'''
	def __init__(self):
		self.jrack = JRack()
		self.choices = {
			"1": self.show_devices,
			"2": self.refresh_device,
			"3": self.add_device,
			"4": self.remove_device,
			"5": self.load_devices,
			"6": self.quit
		}
	
	def display_menu(self):
		print ("""
Rack Menu

1. Show Devices
2. Refresh Devices
3. Add Device
4. Remove Device
5. Load Devices
6. Quit
""")
		
	def run(self):
		'''Display the menu and respond to choices.'''
		while True:
			self.display_menu()
			choice = raw_input("Enter an option: ")				# Change this to "input" when using Python 3
			action = self.choices.get(choice)
			if action:
				action()
			else:
				print("{0} is not a valid choice".format(choice))
	
	def show_devices(self, devices=None):
		''' View all the devices in list.'''
		if not devices:
			devices = self.jrack.devices
		for device in devices:
			print("{0}:\t{1}\t{2}\t{3}\t{4}".format(device.ip, device.model, device.code, device.hostname, device.refresh))
			
	def add_device(self):
		''' Add devices to the list.'''
		ip = raw_input("Enter an ip: ")						# Change this to "input" when using Python 3
		new_device = True
		''' Make sure this device is not already in the list.'''
		for device in self.jrack.devices:
			if ip in device.ip:
				print 'Device {0} already exists.'.format(ip)
				new_device = False
				break
		''' Do this if this is a new device.'''
		if new_device:
			dev = Device(ip, user=Menu.username, password=Menu.password)
			try:
				dev.open()
			except Exception as err:
				print ("Unable to open connection to: " + ip)
			else:
				model = dev.facts['model']
				code = dev.facts['version']
				hostname = dev.facts['hostname']
				self.jrack.new_device(ip, model, code, hostname)
				print("Your new device has been added.")
			dev.close()
			
	def load_devices(self):
		''' Load from a list of devices.'''
		fileList = getFileList(Menu.list_dir)
		if fileList:
			package = getOptionAnswer("Choose a junos package", fileList)
		

	def refresh_device(self):
		pass
	
	def remove_device(self):
		pass
		
	def quit(self):
		print("Thank you for using JRack.")
		sys.exit(0)

			
if __name__ == "__main__":
	Menu().run()