# Author: Tyler Jordan
# File: jscan.py
# Last Modified: 4/21/2016
# Description: main execution file, starts the top-level menu

import os, sys

from jnpr.junos import Device
from jrack import JRack, JDevice

class Menu:
	username = "tjordan"
	password = "ah64dlb"
	
	'''Display a menu and respond to choices when run.'''
	def __init__(self):
		self.jrack = JRack()
		self.choices = {
			"1": self.show_devices,
			"2": self.refresh_device,
			"3": self.add_device,
			"4": self.remove_device,
			"5": self.quit
		}
	
	def display_menu(self):
		print ("""
Rack Menu

1. Show Devices
2. Refresh Devices
3. Add Device
4. Remove Device
5. Quit
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
		if not devices:
			devices = self.jrack.devices
		for device in devices:
			print("{0}: {1}\n{2}\n{3}".format(device.ip, device.model, device.code, device.hostname))
			
	def add_device(self):
		ip = raw_input("Enter an ip: ")							# Change this to "input" when using Python 3
		dev = Device(ip, user=Menu.username, password=Menu.password)
		if dev.open():
			model = dev.facts['model']
			code = dev.facts['version']
			hostname = dev.facts['hostname']
			self.jrack.new_device(ip, model, code, hostname)
			dev.close()
			print("Your new device has been added.")
		else:
			print("Unable to open connection to: " + ip)
		
	def refresh_device(self):
		pass
	
	def remove_device(self):
		pass
		
	def quit(self):
		print("Thank you for using JRack.")
		sys.exit(0)

			
if __name__ == "__main__":
	Menu().run()