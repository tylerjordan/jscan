# Author: Tyler Jordan
# File: jscan.py
# Last Modified: 6/18/2020
# Description: main execution file

import getopt
import sys
import csv
import logging
import datetime
import pprint

from jnpr.junos import Device
from jnpr.junos.utils.sw import SW
from jnpr.junos.exception import *
from jrack import JRack
from utility import *
from os.path import join
from getpass import getpass
from prettytable import PrettyTable
from ncclient.operations.errors import TimeoutExpiredError
from sys import stdout


class Menu:
    username = ""
    password = ""
    port = 22
    upgrade_list = ""

    list_dir = ""
    image_dir = ""
    log_dir = ""
    config_dir = ""
    status_log = ""

    remote_path = "/var/tmp"

    # Display a menu and respond to choices when run.
    def __init__(self):
        self.jrack = JRack()
        self.choices = {
            "1": self.show_devices,
            "2": self.refresh_device,
            "3": self.add_device,
            "4": self.load_devices,
            "5": self.bulk_upgrade,
            "6": self.bulk_reboot,
            "7": self.oper_commands,
            "8": self.set_commands,
            "9": self.pyez_load,
            "10": self.clear_devices,
            "0": self.quit
        }

    # The printed menu
    def display_menu(self):
        print ("""

Rack Menu

1. Show Devices
2. Refresh Devices
3. Add Device
4. Load Devices
5. Bulk Upgrade
6. Bulk Reboot
7. Execute Operational Commands
8. Execute Set Commands
9. PyEZ Load
10. Clear Devices
0. Quit
""")

    def set_dir_format(self):
        # Sets the directory format
        if sys.platform.startswith('win'):
            '''Windows Directory Format'''
            Menu.list_dir = ".\\lists\\"
            Menu.image_dir = ".\\images\\"
            Menu.log_dir = ".\\logs\\"
            Menu.config_dir = ".\\configs\\"
            Menu.status_log = ".\\logs\\Juniper_Status_Log.csv"
        else:
            '''Unix Directory Format'''
            Menu.list_dir = "./lists/"
            Menu.image_dir = "./images/"
            Menu.log_dir = "./logs/"
            Menu.config_dir = "./configs/"
            Menu.status_log = "./logs/Juniper_Status_Log.csv"

        if not exists(Menu.list_dir):
            print("Missing 'lists' directory! Create a directory in jscan directory called 'lists'.")
            return False
        if not exists(Menu.image_dir):
            print("Missing 'images' directory! Create a directory in jscan directory called 'images'.")
            return False
        if not exists(Menu.log_dir):
            print("Missing 'logs' directory! Create a directory in jscan directory called 'logs'.")
            return False

        return True

    def getargs(self, argv):
        # Interprets and handles the command line arguments
        try:
            opts, args = getopt.getopt(argv, "hu:", ["user="])
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
        # Determine the os and set directory paths accordingly
        if Menu.set_dir_format(self):
            # Securely get the user's password
            Menu.password=getpass(prompt="\nEnter your password: ")

            # Display the menu and respond to choices
            while True:
                self.display_menu()
                choice = input("Enter an option: ")				# Change this to "input" when using Python 3
                action = self.choices.get(choice)
                if action:
                    action()
                else:
                    print("{0} is not a valid choice".format(choice))
        else:
            print("Please fix issues and run again.")
            sys.exit(0)

    def show_devices(self):
        # View all the devices in list
        devices = self.jrack.devices
        t = PrettyTable(['IP', 'Model', 'Current Code', 'Target Code', 'Host', 'Last Updated'])
        for device in devices:
            t.add_row([device.ip, device.model, device.curr_code, device.tar_code, device.hostname, device.refresh])
        print(t)

    def add_device(self, ip=None, tar_code=None):
        dot = "."
        # Add devices to the list
        if not ip:
            ip = input("Enter an ip: ")						# Change this to "input" when using Python 3
        new_device = True
        ''' Make sure this device is not already in the list.'''
        print("Adding host {0} ".format(ip),)
        for device in self.jrack.devices:
            if ip in device.ip:
                print("Host: {0} ({1}) already loaded.".format(device.hostname, ip))
                new_device = False
                break
        ''' Do this if this is a new device.'''
        print(dot, end='')
        if new_device:
            dev = Device(ip, user=Menu.username, password=Menu.password)
            attribList = ['model', 'version', 'hostname']
            try:
                print(dot, end='')
                dev.open()
                print(dot, end='')
            except ConnectRefusedError:
                print("\nIssue connecting with NETCONF. Trying to enable NETCONF...")
                if enable_netconf(ip, Menu.username, Menu.password, Menu.port):
                    try:
                        dev.open()
                    except Exception as err:
                        print("\nUnable to open connection to: {0} ERROR: {1}".format(ip, err))
                        return
                    else:
                        print("Continuing with add...")
                        for key in attribList:
                            if key not in dev.facts:
                                print("Missing attribute '{1}', skipping {0}".format(ip, key))
                                dev.facts[key] = 'EMPTY'
                                #dev.close()
                                #return
                        self.jrack.new_device(ip, dev.facts['model'], dev.facts['version'], tar_code, dev.facts['hostname'])
                        print(" {0} ({1}) has been added.".format(ip, dev.facts['hostname']))
            except Exception as err:
                print("Unable to open connection to: {0} ERROR: {1}".format(ip, err))
                return
            else:
                #print dev.facts
                for key in attribList:
                    if key not in dev.facts:
                        print("Missing attribute '{1}', skipping {0}".format(ip, key))
                        # dev.close()
                        return
                self.jrack.new_device(ip, dev.facts['model'], dev.facts['version'], tar_code, dev.facts['hostname'])
                print(" {0} ({1}) has been added.".format(ip, dev.facts['hostname']))
                try:
                    dev.close()
                except TimeoutExpiredError:
                    print("Timed out closing connection")

    def load_devices(self):
        # Load from a list of devices
        filelist = getFileList(Menu.list_dir)
        if filelist:
            Menu.upgrade_list = getOptionAnswer("Choose an upgrade file", filelist)
            with open(join(Menu.list_dir,Menu.upgrade_list), 'r') as infile:
                reader = csv.DictReader(infile)
                print("\n\n----------------------")
                print("Scanning Upgrade CSV")
                print("----------------------\n")
                for row in reader:
                    if row['IP_ADDR'] and not row['UPGRADE_IMG']:
                        self.add_device(row['IP_ADDR'])
                    elif row['UPGRADE_IMG']:
                        self.add_device(row['IP_ADDR'], row['UPGRADE_IMG'])
                    else:
                        print("- Blank Row -")
        else:
            print("No files present in 'lists' directory.")

    def refresh_device(self):
        # Loop through devices and update code and date/time
        changes = False
        print("Please be patient")
        for device in self.jrack.devices:
            print(dot, end='')
            dev = Device(device.ip, user=Menu.username, password=Menu.password)
            try:
                dev.open()
            except Exception as err:
                print("Error opening {0}: {1}".format(device.ip, err))
            else:
                if device.curr_code != dev.facts['version']:
                    old_code = device.curr_code
                    device.curr_code = dev.facts['version']
                    device.refresh = datetime.datetime.now()
                    # Print the changed device
                    print("{0} changed from {1} to {2}".format(device.ip, old_code, device.curr_code))
                    changes = True

        # Display a message if no changes were detected
        if not changes:
            print("\nNo changes!")

    def oper_commands(self):
        # Provide selection for sending a single command or multiple commands from a file
        command_list = []
        while True:
            command = input("Enter an operational command: ")  # Change this to "input" when using Python 3
            if not command:
                break
            else:
                command_list.append(command)

        # Check if user wants to print output to a file
        log_file = None
        if getTFAnswer('\nPrint output to a file'):
            log_file = Menu.log_dir + "oper_cmd_" + datetime.datetime.now().strftime("%Y%m%d-%H%M") + ".log"
            print('Information logged in {0}'.format(log_file))


        output = ""
        screen_and_log(('User: {0}\n').format(Menu.username), log_file)
        # Loop over commands and devices
        for command in command_list:
            for device in self.jrack.devices:
                try:
                    results = op_command(device.ip, device.hostname, command, Menu.username, Menu.password)
                except Exception as err:
                    print("Error running op_command on {0}({1}) ERROR: {2}".format(device.hostname, device.ip, err))
                else:
                    screen_and_log(results, log_file)
                    # Append output to a variable, we'll save when done with output
                    if log_file:
                        output += results
        screen_and_log(("\n" + "*" * 30 + " Commands Completed " + "*" * 30 + "\n"), log_file)

        # Check if a file was requested, if so print output to file
        if log_file:
            try:
                f = open(log_file, 'w')
            except Exception as err:
                print("Problem writing to file {0} ERROR: {1}".format(log_file, err))
            else:
                f.write(output)
                print("Output Written To: {0}".format(log_file))
            f.close()

    def set_commands(self):
        # Provide option for using a file to supply configuration commands
        command_list = []
        if getTFAnswer('\nProvide commands from a file'):
            filelist = getFileList(Menu.config_dir)
            # If the files exist...
            if filelist:
                config_file = getOptionAnswer("Choose a config file", filelist)
                config_file = Menu.config_dir + config_file
                with open(config_file) as f:
                    command_list = f.read().splitlines()
        else:
            # Provide selection for sending a single set command or multiple set commands
            while True:
                command = input("Enter a set command: ")  # Change this to "input" when using Python 3
                if not command:
                    break
                else:
                    command_list.append(command)

        # Create log file for operation
        log_file = Menu.log_dir + "set_cmd_" + datetime.datetime.now().strftime("%Y%m%d-%H%M") + ".log"
        print('\nInformation logged in {0}'.format(log_file))
        screen_and_log(('User: {0}\n').format(Menu.username), log_file)
        screen_and_log("*" * 50 + " COMMANDS " + "*" * 50 + '\n', log_file)
        for command in command_list:
            screen_and_log((" -> {0}\n".format(command)), log_file)

        # Loop over all devices in the rack
        screen_and_log("*" * 50 + " START LOAD " + "*" * 50 + '\n', log_file)
        for device in self.jrack.devices:
            try:
                set_command(device.ip, Menu.username, Menu.password, Menu.port, log_file, command_list)
            except Exception as err:
                print("Problem changing configuration ERROR: {0}".format(err))
        screen_and_log("*" * 50 + " END LOAD " + "*" * 50 + '\n', log_file)

    def clear_devices(self):
        # Loop through devices and delete object instance
        #print("Removing Devices")
        #self.jrack.devices = []

        # Loop for deleting single device
        ip_list = []
        ip_list.append('ALL DEVICES')
        ip_list.append('MULTI SELECT')
        for device in self.jrack.devices:
            ip_list.append(device.ip)

        # Ask user what devices or methods to use for removing devices
        if ip_list:
            ip_del_list = []
            myip = getOptionAnswer("Select a device to delete", ip_list)
            if myip == 'ALL DEVICES':
                self.jrack.devices = []
                return
            elif myip == 'MULTI SELECT':
                ip_list.pop(0)
                ip_list.pop(0)
                ip_del_list = getOptionMultiAnswer("Select devices to delete (ie. 2,3,5...)", ip_list)
            else:
                ip_del_list.append(myip)

            # Delete the devices in the list
            if ip_del_list:
                for del_dev in ip_del_list:
                    #print "Searching for {0}".format(del_dev)
                    for i, dev in enumerate(self.jrack.devices):
                        #print "i: {0} | dev: {1}".format(i, dev.ip)
                        if del_dev == dev.ip:
                            del self.jrack.devices[i]
                            print("Deleted {0}".format(dev.ip))
            else:
                print("No devices selected.")

    def pyez_load(self):
        """ Load configuration to the device using PyEZ methods. Accepts "set" format or "hierarchical" format. The
                load function will determine the file format based on the extension. Here are the recognized extensions
                and what type they represent.

            conf,text,txt - curly-text-style
            set - ascii-text, set-style
            xml - ascii-text, XML

            loadmerge - Performs a 'load merge', merging config data with existing configuration
            loadoverwrite - Replaces ALL existing configuration with what is in the supplied config
            loadreplace - Replaces tagged parts of configuration
        """
        merge_opt = False
        overwrite_opt = False
        format_opt = None
        config_file = ''

        # Find out if commands come from a file or entered directly
        if getTFAnswer('\nProvide commands from a file'):
            filelist = getFileList(Menu.config_dir)
            # If the files exist...
            if filelist:
                config_file = getOptionAnswer("Choose a config file", filelist)
                config_file = Menu.config_dir + config_file
                # Collect the load options
                load_options = ['loadmerge', 'loadoverwrite', 'loadreplace', 'loadset']
                load_option = getOptionAnswer('Which load type', load_options)
                # Set options as necessary
                if load_option == 'loadmerge' or load_option == 'loadset': merge_opt = True
                if load_option == 'loadoverwrite': overwrite_opt = True
                if load_option == 'loadset': format_opt = True
            else:
                print("Fail: No files available in config directory.")
                pass
        # Enter commands in line by line
        else:
            config_file = Menu.config_dir + "temp_conf.set"
            # Try to open the file for writing, will overwrite anything already in the file
            try:
                tempfile = open(config_file, 'w')
            except Exception as err:
                print("Failure opening file {0} | ERROR: {1}".format(config_file, err))
            else:
                # Provide selection for sending a single set command or multiple set commands, add to a file
                while True:
                    command = input("Enter a set command: ")  # Change this to "input" when using Python 3
                    if not command:
                        break
                    else:
                        tempfile.write(command + "\n")
                # Close the file
                tempfile.close()

        # Create log file
        log_file = Menu.log_dir + "pyez_load_" + datetime.datetime.now().strftime("%Y%m%d-%H%M") + ".log"
        print('\nInformation logged in {0}'.format(log_file))
        screen_and_log(("User: {0}").format(Menu.username), log_file)

        # Display the commands provided
        screen_and_log("\n" + "*" * 50 + " COMMANDS " + "*" * 50 + "\n", log_file)
        try:
            myfile = open(config_file, 'r')
        except Exception as err:
            print("Failure opening {0} | ERROR: {1}".format(config_file, err))
        else:
            for line in myfile.readlines():
                screen_and_log((" -> {0}".format(line)), log_file)
            myfile.close()

        # Loop over the devices
        screen_and_log("\n" + "*" * 50 + " START LOAD " + "*" * 50 + "\n", log_file)
        for device in self.jrack.devices:
            results = load_with_pyez(merge_opt, overwrite_opt, format_opt, config_file, log_file, device.ip, device.hostname, Menu.username, Menu.password)
        screen_and_log("*" * 50 + " END LOAD " + "*" * 50 + "\n", log_file)

    def upgrade_device(self, ip, hostname, tar_code, reboot="askReboot"):
        # Upgrade single device
        # Status dictionary for post-upgrade reporting
        statusDict = {}
        if Menu.upgrade_list == '':
            statusDict['Upgrade_List'] = 'Juniper-Upgrade_' + Menu.username
        else:
            statusDict['Upgrade_List'] = Menu.upgrade_list
        statusDict['Upgrade_Start'] = ''
        statusDict['Upgrade_Finish'] = ''
        statusDict['IP'] = ip
        statusDict['Connected'] = 'N'
        statusDict['OS_installed'] = 'N'
        statusDict['Rebooted'] = 'N'
        statusDict['IST_Confirm_Loaded'] = ''
        statusDict['IST_Confirm_Rebooted'] = ''
        statusDict['Comments'] = ''

        # Start Logging
        now = datetime.datetime.now()
        date_time = now.strftime("%Y-%m-%d-%H%M")
        install_log = Menu.log_dir + "juniper-install-LOG_" + date_time + "_" + Menu.username + ".log"
        logging.basicConfig(filename=install_log, level=logging.INFO, format='%(asctime)s:%(name)s: %(message)s')
        logging.getLogger().name = ip
        print('Information logged in {0}'.format(install_log))

        # Upgrade Information
        self.do_log("Device: {0} ({1})".format(hostname, ip))
        self.do_log("JunOS: {0}".format(tar_code))

        # Verify package exists before starting upgrade process
        fullpathfile = Menu.image_dir + tar_code
        if os.path.isfile(fullpathfile):
            dev = Device(ip, user=Menu.username, password=Menu.password)
            self.do_log('\n')
            self.do_log('------------------------- Opening connection to: {0} -------------------------\n'.format(ip))
            self.do_log('User: {0}'.format(Menu.username))
            # Try to open a connection to the device
            try:
                dev.open()
            # If there is an error when opening the connection, display error and exit upgrade process
            except Exception as err:
                sys.stderr.write('Cannot connect to device {0} : {1}'.format(ip, err))
            # If
            else:
                # Record connection achieved
                statusDict['Connected'] = 'Y'
                # Increase the default RPC timeout to accommodate install operations
                dev.timeout = 600
                # Create an instance of SW
                sw = SW(dev)
                try:
                    # Logging...
                    self.do_log('Starting the software upgrade process: {0}'.format(tar_code))
                    now = datetime.datetime.now()
                    statusDict['Upgrade_Start'] = now.strftime("%Y-%m-%d %H:%M")
                    self.do_log('Timestamp: {0}'.format(statusDict['Upgrade_Start']))

                    # Actual Upgrade Function
                    ok = sw.install(package=fullpathfile, remote_path=Menu.remote_path, progress=True, validate=True)
                    # Failed install method...
                    # ok = sw.install(package=fullPathFile, remote_path=Menu.remote_path, progress=self.update_progress, validate=True)
                except Exception as err:
                    msg = 'Unable to install software, {0}'.format(err)
                    self.do_log(msg, level='error')
                else:
                    if ok is True:
                        # Logging...
                        statusDict['OS_installed'] = 'Y'
                        self.do_log('Software installation complete.')
                        now = datetime.datetime.now()
                        statusDict['Upgrade_Finish'] = now.strftime("%Y-%m-%d %H:%M")
                        self.do_log('Timestamp: {0}'.format(statusDict['Upgrade_Finish']))
                        # Check rebooting status...
                        if reboot == "askReboot":
                            answer = getYNAnswer('Would you like to reboot')
                            if answer == 'y':
                                reboot = "doReboot"
                            else:
                                reboot = "noReboot"
                        if reboot == "doReboot":
                            rsp = sw.reboot()
                            statusDict['Rebooted'] = 'Y'
                            self.do_log('Upgrade pending reboot cycle, please be patient.')
                            self.do_log(rsp)
                            # Open a command terminal to monitor device connectivity
                            # os.system("start cmd /c ping -t " + ip)
                        elif reboot == "noReboot":
                            self.do_log('Reboot NOT performed. System must be rebooted to complete upgrade.')

                # End the NETCONF session and close the connection
                dev.close()
                self.do_log('\n')
                self.do_log('------------------------- Closed connection to: {0} -------------------------\n'.format(ip))
        else:
            msg = 'Software package does not exist: {0}. '.format(fullpathfile)
            sys.exit(msg + '\nExiting program')

        return statusDict

    def bulk_upgrade(self):
        # Upgrade the devices that are currently loaded
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
        t = PrettyTable(['IP', 'Model', 'Current Code', 'Target Code', 'Reboot'])
        for device in devices:
            t.add_row([device.ip, device.model, device.curr_code, device.tar_code, reboot])
        print(t)
        # Last confirmation before entering loop
        verified = getYNAnswer("Please Verify the information above. Continue")

        # Upgrade Loop
        # verified = 'y'
        if verified == 'y':

            # Loop over all devices in list
            for device in devices:
                statusDict = self.upgrade_device(device.ip, device.hostname, device.tar_code, reboot)
                # Add status results to list
                statusList.append(statusDict)
            '''
            # StatusList Test
            statusList = [
                {'Upgrade_List': 'Juniper-Upgrade_aabcct3.csv', 'Upgrade_Start': '7/26/2016 09:25',  'Upgrade_Finish': '7/26/2016 09:39', 'IP': '10.10.10.1', 'Connected': 'Y', 'OS_installed': 'Y', 'Rebooted': 'Y'},
                {'Upgrade_List': 'Juniper-Upgrade_aabcct3.csv', 'Upgrade_Start': '7/26/2016 09:40',  'Upgrade_Finish': '7/26/2016 09:54', 'IP': '10.10.10.2', 'Connected': 'Y', 'OS_installed': 'Y', 'Rebooted': 'N'},
                {'Upgrade_List': 'Juniper-Upgrade_aabcct3.csv', 'Upgrade_Start': '7/26/2016 09:55',  'Upgrade_Finish': '7/26/2016 10:10', 'IP': '10.10.10.3', 'Connected': 'Y', 'OS_installed': 'N', 'Rebooted': 'N'},
                {'Upgrade_List': 'Juniper-Upgrade_aabcct3.csv', 'Upgrade_Start': '7/26/2016 10:15',  'Upgrade_Finish': '7/26/2016 10:25', 'IP': '10.10.10.4', 'Connected': 'N', 'OS_installed': 'N', 'Rebooted': 'N'}
            ]
            '''
            # Create CSV
            keys = ['Upgrade_List', 'Upgrade_Start', 'Upgrade_Finish', 'IP', 'Connected', 'OS_installed', 'Rebooted']
            listDictCSV(statusList, Menu.status_log, keys)

            # Tabulate and Print Results
            resultsDict = tabulateUpgradeResults(statusList)
            print("\n\n---------------")
            print("Process Summary")
            print("---------------")
            print("Successful (rebooted): {0}".format(len(resultsDict['success_rebooted'])))
            print("Successful (not rebooted): {0}".format(len(resultsDict['success_not_rebooted'])))
            print("Unable to connect: {0}".format(len(resultsDict['connect_fails'])))
            for myfailed in resultsDict['connect_fails']:
                print("\t{0}".format(myfailed))
            print("Software install failed: {0}".format(len(resultsDict['software_install_fails'])))
            for myfailed in resultsDict['software_install_fails']:
                print("\t{0}".format(myfailed))
            print("\nTOTAL DEVICES: {0}".format(resultsDict['total_devices']))
            print("---------------")
        else:
            print("Aborted Upgrade! Returning to Main Menu.")

    def bulk_reboot(self):
        # Reboots the selected devices
        devices = self.jrack.devices

        # List for all status dictionaries for each device
        statusList = []

        # Display Procedure
        print("\n\n----------------------")
        print("Upgrade Specifications")
        print("----------------------")
        t = PrettyTable(['IP', 'Model', 'Before Reboot', 'After Reboot'])
        for device in devices:
            t.add_row([device.ip, device.model, device.curr_code, device.tar_code])
        print(t)
        # Last confirmation before entering loop
        verified = getYNAnswer("Please Verify the information above. Continue")

        # Upgrade Loop
        # verified = 'y'
        if verified == 'y':
            # Loop over all devices in list
            print("\n\n--------------------")
            print("Rebooting Devices")
            print("--------------------\n")
            for device in devices:
                try:
                    statusDict = self.reboot_device(device.ip, device.hostname)
                except Exception as err:
                    msg = 'Reboot function failed, {0}'.format(err)
                    self.do_log(msg, level='error')
                else:
                    # Add status results to list
                    statusList.append(statusDict)
                    # Open a command terminal to monitor device connectivity
                    # os.system("start cmd /c ping -t " + device.ip)
            '''
            # Test Dictionary List
            statusList = [
                {'Upgrade_List': 'Juniper-Upgrade_aabcct3.csv', 'Upgrade_Start': '-',  'Upgrade_Finish': '-', 'IP': '10.10.10.1', 'Connected': 'Y', 'OS_installed': '-', 'Rebooted': 'Y', 'IST_Confirm_Loaded': '', 'IST_Confirm_Rebooted': '', 'Comments': ''},
                {'Upgrade_List': 'Juniper-Upgrade_aabcct3.csv', 'Upgrade_Start': '-',  'Upgrade_Finish': '-', 'IP': '10.10.10.2', 'Connected': 'Y', 'OS_installed': '-', 'Rebooted': 'Y', 'IST_Confirm_Loaded': '', 'IST_Confirm_Rebooted': '', 'Comments': ''},
                {'Upgrade_List': 'Juniper-Upgrade_aabcct3.csv', 'Upgrade_Start': '-',  'Upgrade_Finish': '-', 'IP': '10.10.10.3', 'Connected': 'Y', 'OS_installed': '-', 'Rebooted': 'N', 'IST_Confirm_Loaded': '', 'IST_Confirm_Rebooted': '', 'Comments': ''},
                {'Upgrade_List': 'Juniper-Upgrade_aabcct3.csv', 'Upgrade_Start': '-',  'Upgrade_Finish': '-', 'IP': '10.10.10.4', 'Connected': 'N', 'OS_installed': '-', 'Rebooted': 'N', 'IST_Confirm_Loaded': '', 'IST_Confirm_Rebooted': '', 'Comments': ''}
            ]
            '''
            # Create CSV
            keys = [ 'Upgrade_List', 'Upgrade_Start', 'Upgrade_Finish', 'IP', 'Connected', 'OS_installed', 'Rebooted', 'IST_Confirm_Loaded', 'IST_Confirm_Rebooted', 'Comments' ]
            listDictCSV(statusList, Menu.status_log, keys)

            # Tabulate and Print Results
            resultsDict = tabulateRebootResults(statusList)
            print("\n\n---------------")
            print("Process Summary")
            print("---------------")
            print("Rebooted: {0}".format(len(resultsDict['rebooted'])))
            print("Reboot Failed: {0}".format(len(resultsDict['not_rebooted'])))
            for myfailed in resultsDict['not_rebooted']:
                print("\t{0}".format(myfailed))
            print("Unable to connect: {0}".format(len(resultsDict['connect_fails'])))
            for myfailed in resultsDict['connect_fails']:
                print("\t{0}".format(myfailed))

            print("\nTOTAL DEVICES: {0}").format(resultsDict['total_devices'])
            print("---------------")
        else:
            print("Aborted Upgrade! Returning to Main Menu.")

    def reboot_device(self, ip, hostname):
        # Reboots a device
        # Status dictionary for post-upgrade reporting
        statusDict = {}
        if Menu.upgrade_list == '':
            statusDict['Upgrade_List'] = 'Juniper-Upgrade_' + Menu.username
        else:
            statusDict['Upgrade_List'] = Menu.upgrade_list
        statusDict['Upgrade_Start'] = ''
        statusDict['Upgrade_Finish'] = '-'
        statusDict['IP'] = ip
        statusDict['Connected'] = 'N'
        statusDict['OS_installed'] = '-'
        statusDict['Rebooted'] = 'N'
        statusDict['IST_Confirm_Loaded'] = '-'
        statusDict['IST_Confirm_Rebooted'] = ''
        statusDict['Comments'] = ''

        # Start the logging
        now = datetime.datetime.now()
        date_time = now.strftime("%Y-%m-%d-%H%M")
        reboot_log = Menu.log_dir + "juniper-reboot-LOG_" + date_time + "_" + Menu.username + ".log"
        logging.basicConfig(filename=reboot_log, level=logging.INFO, format='%(asctime)s:%(name)s: %(message)s')
        logging.getLogger().name = ip
        print('Information logged in {0}'.format(reboot_log))

        # Display basic information
        self.do_log("Device: {0} ({1})".format(hostname, ip))
        now = datetime.datetime.now()
        formattime = now.strftime("%Y-%m-%d %H:%M")
        self.do_log("Timestamp: {0}".format(formattime))

        # Verify package exists before starting upgrade process
        dev = Device(ip, user=Menu.username, password=Menu.password)
        # Try to open a connection to the device
        try:
            self.do_log('\n')
            self.do_log('------------------------- Opening connection to: {0} -------------------------\n'.format(ip))
            self.do_log('User: {0}'.format(Menu.username))
            dev.open()
        # If there is an error when opening the connection, display error and exit upgrade process
        except Exception as err:
            sys.stderr.write('Cannot connect to device: {0}\n'.format(err))
        else:
            # Record connection achieved
            statusDict['Connected'] = 'Y'

            # Increase the default RPC timeout to accommodate install operations
            dev.timeout = 600
            # Create an instance of SW
            sw = SW(dev)

            # Logging
            now = datetime.datetime.now()
            statusDict['Upgrade_Start'] = now.strftime("%Y-%m-%d %H:%M")
            self.do_log('Timestamp: {0}'.format(statusDict['Upgrade_Start']))
            self.do_log('Beginning reboot cycle, please be patient.')

            # Attempt to reboot
            try:
                rsp = sw.reboot()
                self.do_log(rsp)
            except Exception as err:
                msg = 'Unable to reboot system, {0}'.format(err)
                self.do_log(msg, level='error')
            else:
                # Record reboot
                statusDict['Rebooted'] = 'Y'

            # End the NETCONF session and close the connection
            dev.close()
            self.do_log('\n')
            self.do_log('------------------------- Closed connection to: {0} -------------------------\n'.format(ip))

        return statusDict

    def do_log(self, msg, level='info'):
        getattr(logging, level)(msg)
        print("--> " + msg)

    def update_progress(self, report):
        # log the progress of the installing process
        print("--> " + report)
        self.do_log(report)

    def quit(self):
        print("Thank you for using JRack. Juniper Your Network!")
        sys.exit(0)

if __name__ == "__main__":
    Menu().getargs(sys.argv[1:])
    Menu().run()