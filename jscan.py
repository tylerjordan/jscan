# Author: Tyler Jordan
# File: jscan.py
# Last Modified: 7/19/2016
# Description: main execution file, starts the top-level menu

import os, sys, getopt, csv
import utility, logging
import datetime

from jnpr.junos import Device
from jnpr.junos.utils.sw import SW
from jrack import JRack, JDevice
from utility import *
from os.path import join
from datetime import datetime
from getpass import getpass

class Menu:
	username = ""
	password = ""
	list_dir = ".\\lists\\"
	image_dir = ".\\images\\"
	log_dir = ".\\logs\\"
	remote_path = "/var/tmp"
	logfile = ".\\logs\\install.log"
	
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
	def getargs(self, argv):
		''' Interprets and handles the command line arguments '''
		try:
			opts, args = getopt.getopt(argv,"hu:",["user="])
		except getopt.GetoptError:
			print("jscan.py -u <username>")
			sys.exit(2)
		for opt, arg in opts:
			if opt == '-h':
				print("jscan.py -u <username>")
				sys.exit()
			elif opt in ("-u", "--user"):
				Menu.username = arg
		
	def run(self):
		Menu.password=getpass(prompt="\nEnter your password: ")
		'''Display the menu and respond to choices.'''
		while True:
			self.display_menu()
			choice = raw_input("Enter an option: ")				# Change this to "input" when using Python 3
			action = self.choices.get(choice)
			if action:
				action()
			else:
				print("{0} is not a valid choice".format(choice))
	
	def show_devices(self):
		''' View all the devices in list.'''
		devices = self.jrack.devices
		print("--- IP ---\t--- Model ---\t--- Curr Code ---\t--- New Code ---\t--- Host ---\t--- Last Updated ---")
		if not devices:
			print(" - No Devices Loaded - ")
		for device in devices:
			print("{0}:\t{1}\t{2}\t{3}\t{4}\t{5}".format(device.ip, device.model, device.curr_code, device.tar_code, device.hostname, device.refresh))
		
	def add_device(self, ip=None, tar_code=None):
		''' Add devices to the list.'''
		if not ip:
			ip = raw_input("Enter an ip: ")						# Change this to "input" when using Python 3
		new_device = True
		''' Make sure this device is not already in the list.'''
		for device in self.jrack.devices:
			if ip in device.ip:
				print("Host: {0} ({1}) already loaded.".format(hostname, ip))
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
				curr_code = dev.facts['version']
				hostname = dev.facts['hostname']
				self.jrack.new_device(ip, model, curr_code, tar_code, hostname)
				print("Host: {0} ({1}) has been added.".format(hostname, ip))
				dev.close()
			
	def load_devices(self):
		''' Load from a list of devices.'''
		fileList = getFileList(Menu.list_dir)
		if fileList:
			package = getOptionAnswer("Choose a list file", fileList)
			with open(join(Menu.list_dir,package), 'r') as infile:
				reader = csv.DictReader(infile)
				print("\n\n----------------------")
				print("Scanning CSV")
				print("----------------------\n")
				for row in reader:
					if not row['UPGRADE_IMG']:
						self.add_device(row['IP_ADDR'])
					else:
						self.add_device(row['IP_ADDR'], row['UPGRADE_IMG'])

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
	
	def upgrade_device(self, ip, hostname, tar_code, reboot="askReboot"):
		''' Upgrade single device. '''
		# Status dictionary for post-upgrade reporting
		statusDict = {}
		statusDict['ip'] = ip
		statusDict['connected'] = 0
		statusDict['os_installed'] = 0
		statusDict['rebooted'] = 0
		
		# Upgrade Process
		print("\n\nStarting Upgrade Process on Device: {0} ({1})".format(hostname, ip))
		print("Timestamp: {0}".format(datetime.now()))
		print("JunOS: {0}".format(tar_code))
		
		logging.basicConfig(filename=Menu.logfile, level=logging.INFO, format='%(asctime)s:%(name)s: %(message)s')
		logging.getLogger().name = ip
		sys.stdout.write('Information logged in {0}\n'.format(Menu.logfile))
	
		# Verify package exists before starting upgrade process
		fullPathFile = Menu.image_dir + tar_code
		if (os.path.isfile(fullPathFile)):
			dev = Device(ip,user=Menu.username,password=Menu.password)
			# Try to open a connection to the device
			try:
				self.do_log('\n')
				self.do_log('------------------------- Opening connection to: {0} -------------------------\n'.format(ip))
				self.do_log('User: {0}'.format(Menu.username))
				dev.open()
			# If there is an error when opening the connection, display error and exit upgrade process
			except Exception as err:
				sys.stderr.write('Cannot connect to device: {0}\n'.format(err))
			# If
			else:
				# Record connection achieved
				statusDict['connected'] = 1
				# Increase the default RPC timeout to accommodate install operations
				dev.timeout = 300
				# Create an instance of SW
				sw = SW(dev)
				try:
					self.do_log('Starting the software upgrade process: {0}'.format(tar_code))
					print("Timestamp: {0}".format(datetime.now()))
					ok = sw.install(package=fullPathFile, remote_path=Menu.remote_path, progress=True, validate=True)
					# Failed install method...
					#ok = sw.install(package=fullPathFile, remote_path=Menu.remote_path, progress=self.update_progress, validate=True)
				except Exception as err:
					msg = 'Unable to install software, {0}'.format(err) 
					self.do_log(msg, level='error')
				else:
					if ok is True:
						statusDict['os_installed'] = 1
						self.do_log('Software installation complete.')
						print("Timestamp: {0}".format(datetime.now()))
						if reboot == "askReboot":
							answer = getYNAnswer('Would you like to reboot')
							if answer == 'y':
								reboot = "doReboot"
							else:
								reboot = "noReboot"
						if reboot == "doReboot":
							rsp = sw.reboot()
							statusDict['rebooted'] = 1
							self.do_log('Upgrade pending reboot cycle, please be patient.')
							self.do_log(rsp)
						elif reboot == "noReboot":
							self.do_log('Reboot NOT performed. System must be rebooted to complete upgrade.')
				
				# End the NETCONF session and close the connection
				dev.close()
				self.do_log('\n')
				self.do_log('------------------------- Closed connection to: {0} -------------------------\n'.format(ip))
		else:
			msg = 'Software package does not exist: {0}. '.format(fullPathFile)
			sys.exit(msg + '\nExiting program')
			
		return statusDict

	def bulk_upgrade(self):
		''' Upgrade the devices that are currently loaded'''
		devices = self.jrack.devices
		
		# List for all status dictionaries for each device
		statusList = []
		
		# Get Reboot Preference
		reboot = None
		myoptions = ['Reboot ALL devices automatically', 'Do not reboot ANY device', 'Ask for ALL devices']
		answer = getOptionAnswerIndex("How would you like to handle reboots", myoptions)

		if answer == "1": reboot = "doReboot"
		elif answer == "2": reboot = "noReboot"
		elif answer == "3": reboot = "askReboot"
		
		# Get target codes if necessary and verify those that are already defined
		print("\n\n--------------------")
		print("Verifying Images")
		print("--------------------\n")
		for device in devices:
			if device.tar_code == None:
				# No code defined, ask for one...
				print("{0} does not have an image, please select one...".format(device.ip))
				device.tar_code = getCode(device, Menu.image_dir)
			else:
				# Make sure file exists. If not, ask for one...
				if not isfile(Menu.image_dir + device.tar_code):
					print("Unable to find file: {0} ".format(device.tar_code))
					device.tar_code = getCode(device, Menu.image_dir)
				else:
					print("{0} has a valid image".format(device.ip))
				
		print("\n\n----------------------")
		print("Upgrade Specifications")
		print("----------------------")
		print("--- IP ---\t--- Model ---\t--- Curr Code ---\t\t--- Target Code ---\t\t--- Reboot ---")
		for device in devices:
			print("{0}:\t{1}\t{2}\t{3}\t{4}".format(device.ip, device.model, device.curr_code, device.tar_code, reboot))
		print("-------------------------------------")
		# Last confirmation before entering loop
		verified = getYNAnswer("Please Verify the information above. Continue")
		
		# Upgrade Loop
		if verified == 'y':
			for device in devices:
				statusDict = self.upgrade_device(device.ip, device.hostname, device.tar_code, reboot)
				# Add status results to list
				statusList.append(statusDict)
			# Create CSV
			keys = [ 'ip', 'connected', 'os_installed', 'rebooted' ]
			listDictCSV(statusList, Menu.log_dir, 'statuslog.csv', keys)
			
			# Tabulate and Print Results
			resultsDict = tabulateResults(statusList)
			print("\n\n---------------")
			print("Process Summary")
			print("---------------")
			print("Successful (rebooted): {0}".format(len(resultsDict['success_rebooted'])))
			print("Successful (not rebooted: {0}".format(len(resultsDict['success_not_rebooted'])))
			print("Unable to connect: {0}".format(len(resultsDict['connect_fails'])))
			print("Software install failed: {0}".format(len(resultsDict['software_install_fails'])))
			print("\nTOTAL DEVICES: {0}").format(resultDict['total_devices'])
			print("---------------")
		else:
			print("Aborted Upgrade! Returning to Main Menu.")

	def do_log(self, msg, level='info'):
	    getattr(logging, level)(msg)
	    print("--> " + msg)

	def update_progress(self, dev, report):
	    # log the progress of the installing process
	    print("--> " + report)
	    self.do_log(report)

	def quit(self):
		print("Thank you for using JRack.")
		sys.exit(0)

if __name__ == "__main__":
	Menu().getargs(sys.argv[1:])
	Menu().run()