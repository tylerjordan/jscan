# Author: Tyler Jordan
# File: jscan.py
# Last Modified: 7/19/2016
# Description: main execution file, starts the top-level menu

import os, sys
import utility, logging

from jnpr.junos import Device
from jnpr.junos.utils.sw import SW
from jrack import JRack, JDevice
from utility import *
from os.path import join

class Menu:
	username = "admin"
	password = "jlab123$"
	list_dir = ".\\lists\\"
	image_dir = ".\\images\\"
	remote_path = '/var/tmp'
	logfile = '.\\logs\\install.log'
	
	'''Display a menu and respond to choices when run.'''
	def __init__(self):
		self.jrack = JRack()
		self.choices = {
			"1": self.show_devices,
			"2": self.refresh_device,
			"3": self.add_device,
			"4": self.remove_device,
			"5": self.load_devices,
			"6": self.bulk_upgrade,
			"7": self.quit
		}
	
	def display_menu(self):
		print ("""
Rack Menu

1. Show Devices
2. Refresh Devices
3. Add Device
4. Remove Device
5. Load Devices
6. Upgrade Devices
7. Quit
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
			
	def add_device(self, ip=None):
		''' Add devices to the list.'''
		if not ip:
			ip = raw_input("Enter an ip: ")						# Change this to "input" when using Python 3
		new_device = True
		''' Make sure this device is not already in the list.'''
		for device in self.jrack.devices:
			if ip in device.ip:
				print("Device {0} already loaded.".format(ip))
				new_device = False
				break
		''' Do this if this is a new device.'''
		if new_device:
			dev = Device(ip, user=Menu.username, password=Menu.password)
			try:
				dev.open()
			except Exception as err:
				print("Unable to open connection to: " + ip)
			else:
				model = dev.facts['model']
				code = dev.facts['version']
				hostname = dev.facts['hostname']
				self.jrack.new_device(ip, model, code, hostname)
				print("Host: " + hostname + " has been added.")
				dev.close()
			
	def load_devices(self):
		''' Load from a list of devices.'''
		fileList = getFileList(Menu.list_dir)
		if fileList:
			package = getOptionAnswer("Choose a list file", fileList)
			with open(join(Menu.list_dir,package), 'r') as infile:
				data = infile.read()
			for ip in data.splitlines():
				self.add_device(ip)	

	def refresh_device(self):
		''' Loop through devices and update code and date/time '''
		for device in self.jrack.devices:
			dev = Device(device.ip, user=Menu.username, password=Menu.password)
			try:
				dev.open()
			except Exception as err:
				print("Unable to open connection to: " + ip)
			else:
				if device.code != dev.facts['version']:
					device.code = dev.facts['version']
					device.refresh = datetime.now()
					print("Changed Code")
				else:
					print("Nothing Changed")

	def remove_device(self):
		''' Loop through devices and delete object instance '''
		ip = getInputAnswer("Enter the IP of device you want to remove")
		
		for device in self.jrack.devices:
			if device.ip == ip:
				del device
				print("Deleted Device: " + ip)
			else:
				print("Skipping Device: " + ip )
	
	def upgrade_device(self, ip, new_code, reboot=None):
		''' Upgrade single device. '''
		print("Loading JunOS: " + new_code + " ...")
		fullPathFile = Menu.image_dir + new_code
		logging.basicConfig(filename=Menu.logfile, level=logging.INFO, format='%(asctime)s:%(name)s: %(message)s')
		logging.getLogger().name = ip
		sys.stdout.write('Information logged in {0}\n'.format(Menu.logfile))
	
		# Verify package exists before starting upgrade process
		if (os.path.isfile(fullPathFile)):
			dev = Device(ip,user=Menu.username,password=Menu.password)
			# Try to open a connection to the device
			try:
				self.do_log('\n------------------------- Opening connection to: {0} -------------------------\n'.format(ip))
				dev.open()
			# If there is an error when opening the connection, display error and exit upgrade process
			except Exception as err:
				sys.stderr.write('Cannot connect to device: {0}\n'.format(err))
			# If
			else:
				# Increase the default RPC timeout to accommodate install operations
				dev.timeout = 300
				# Create an instance of SW
				sw = SW(dev)
				try:
					self.do_log('Starting the software upgrade process: {0}'.format(new_code))
					ok = sw.install(package=fullPathFile, remote_path=Menu.remote_path, progress=True, validate=True)
				except Exception as err:
					msg = 'Unable to install software, {0}'.format(err) 
					self.do_log(msg, level='error')
				else:
					if ok is True:
						self.do_log('Software installation complete.')
						if reboot == None:
							answer = getYNAnswer('Would you like to reboot')
							if answer == 'y':
								reboot = True
							else:
								reboot = False
						if reboot is True:
							rsp = sw.reboot()
							self.do_log('Upgrade pending reboot cycle, please be patient.')
							self.do_log(rsp)
						else:
							self.do_log('Reboot NOT performed. System must be rebooted to complete upgrade.')
					# End the NETCONF session and close the connection
				self.do_log('\n------------------------- Closing connection to: {0} -------------------------\n'.format(ip))
				dev.close()
		else:
			msg = 'Software package does not exist: {0}. '.format(fullPathFile)
			sys.exit(msg + '\nExiting program')

	def bulk_upgrade(self):
		''' Upgrade the devices that are currently loaded'''
		devices = self.jrack.devices
		# Keys for list of dictionaries
		listDict = []
		mykeys = ['ip_addr', 'model', 'old_code', 'new_code', 'reboot']
		
		# Get Reboot Preference
		reboot = None
		myoptions = ['Reboot ALL devices automatically', 'Do not reboot ANY device', 'Ask for ALL devices']
		answer = getOptionAnswer("How would you like to handle reboots", myoptions)
		if answer == "1": reboot = True
		elif answer == "2": reboot = False
		
		# Get Code Upgrade For Each Device or Load From a CSV
		for device in devices:
			print("*****| " + device.hostname + " |*****")
			print("IP: " + device.ip)
			print("Model: " + device.model)
			print("Current Code: " + device.code)
			print("********************************************")
			
			myvalues = []
			filteredList = jinstallFilter(Menu.image_dir, device.model)
			if filteredList:
				host = ''
				new_code = getOptionAnswer("Choose an image", filteredList)
				myvalues.append(device.ip)
				myvalues.append(device.model)
				myvalues.append(device.code)
				myvalues.append(new_code)
				myvalues.append(reboot)
				# Assign new diectionary to List
				listDict.append({mykeys[n]:myvalues[n] for n in range(0,len(mykeys))})
			else:
				print("No images available.")
			print("-------")
		print("-------")
		print("------- Upgrade Specifications --------")
		for item in listDict:
			print("{0}:\t{1}\t{2}\t{3}\t{4}".format(item['ip_addr'], item['model'], item['old_code'], item['new_code'], item['reboot']))
		print("-------------------------------------")
		
		# Upgrade Loop
		for item in listDict:
			keepGoing = getYNAnswer("Proceed to device; " + item['ip_addr'])
			if keepGoing == 'y':
				self.upgrade_device(item['ip_addr'], item['new_code'], item['reboot'])
			else:
				print("Skipped: " + item['ip_addr'])

	def do_log(self, msg, level='info'):
	    getattr(logging, level)(msg)

	def update_progress(self, dev, report):
	    # log the progress of the installing process
	    print("--> " + report)
	    self.do_log(report)

	def quit(self):
		print("Thank you for using JRack.")
		sys.exit(0)

if __name__ == "__main__":
	Menu().run()