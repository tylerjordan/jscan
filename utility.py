# File: utility.py
# Author: Tyler Jordan
# Modified: 9/29/2016
# Purpose: Assist CBP engineers with Juniper configuration tasks

import sys, re, os
import fileinput
import glob
import code
import paramiko  # https://github.com/paramiko/paramiko for -c -mc -put -get
import logging

from os import listdir
from os.path import isfile, join, exists
from jnpr.junos import Device
from jnpr.junos.utils.config import Config
from jnpr.junos.exception import ConnectError
from jnpr.junos.exception import LockError
from jnpr.junos.exception import UnlockError
from jnpr.junos.exception import ConfigLoadError
from jnpr.junos.exception import CommitError
from ncclient import manager  # https://github.com/ncclient/ncclient
from ncclient.transport import errors

#--------------------------------------
# ANSWER METHODS
#--------------------------------------
# Method for asking a question that has a single answer, returns answer
def getOptionAnswer(question, options):
    answer = ""
    loop = 0
    while not answer:
        print question + '?:\n'
        for option in options:
            loop += 1
            print '[' + str(loop) + '] -> ' + option
        answer = raw_input('Your Selection: ')
        try:
            if int(answer) >= 1 and int(answer) <= loop:
                index = int(answer) - 1
                return options[index]
        except Exception as err:
            print "Invalid Entry - ERROR: {0}".format(err)
        else:
            print "Bad Selection"
        answer = ""
        loop = 0

# Method for asking a question that has a single answer, returns answer index
def getOptionAnswerIndex(question, options):
    answer = ""
    loop = 0
    while not answer:
        print question + '?:\n'
        for option in options:
            loop += 1
            print '[' + str(loop) + '] -> ' + option
        answer = raw_input('Your Selection: ')
        try:
            if int(answer) >= 1 and int(answer) <= loop:
                return answer
        except Exception as err:
            print "Invalid Entry - ERROR: {0}".format(err)
        else:
            print "Bad Selection"
        answer = ""
        loop = 0

# Method for asking a user input question
def getInputAnswer(question):
    answer = ""
    while not answer:
        answer = raw_input(question + '?: ')
    return answer

# Method for asking a Y/N question
def getYNAnswer(question):
    answer = ""
    while not answer:
        answer = raw_input(question + '?(y/n): ')
        if answer == 'Y' or answer == 'y':
            answer = 'y'
        elif answer == 'N' or answer == 'n':
            answer = 'n'
        else:
            print "Bad Selection"
            answer = ""
    return answer

# Method for asking a Y/N question, return True or False
def getTFAnswer(question):
    answer = False
    while not answer:
        ynanswer = raw_input(question + '?(y/n): ')
        if ynanswer == 'Y' or ynanswer == 'y':
            answer = True
            return answer
        elif ynanswer == 'N' or ynanswer == 'n':
            answer = False
            return answer
        else:
            print "Bad Selection"

# Return list of files from a directory
def getFileList(mypath):
    fileList = []
    if exists(mypath):
        try:
            for afile in listdir(mypath):
                if isfile(join(mypath,afile)):
                    fileList.append(afile)
        except Exception as err:
            print "Error accessing files {0} - ERROR: {1}".format(mypath, err)
    else:
        print "Path: {0} does not exist!".format(mypath)
    return fileList

# Method for requesting IP address target
def getTarget():
    print 64*"="
    print "= Scan Menu" + 52*" " + "="
    print 64*"="
    # Loop through the IPs from the file "ipsitelist.txt"
    loop = 0
    list = {};
    for line in fileinput.input('ipsitelist.txt'):
        # Print out all the IPs/SITEs
        loop += 1
        ip,site = line.split(",")
        list[str(loop)] = ip;
        print '[' + str(loop) + '] ' + ip + ' -> ' + site.strip('\n')

    print "[c] Custom IP"
    print "[x] Exit"
    print "\n"

    response = ""
    while not response:
        response = raw_input("Please select an option: ")
        if response >= "1" and response <= str(loop):
            return list[response]
        elif response == "c":
            capturedIp = ""
            while not capturedIp:
                capturedIp = raw_input("Please enter an IP: ")
                return capturedIp
        elif response == "x":
            response = "exit"
            return response
        else:
            print "Bad Selection"

# Common method for accessing multiple routers
def chooseDevices():
    # Define the routers to deploy the config to (file/range/custom)
    print "**** Configuration Deployment ****"
    method_resp = getOptionAnswer('How would you like to define the devices', ['file', 'range', 'custom'])
    ip_list = []
    # Choose a file from a list of options
    if method_resp == "file":
        print "Defining a file..."
        path = '.\ips\*.ips'
        files=glob.glob(path)
        file_resp = getOptionAnswer('Choose a file to use', files)

        # Print out all the IPs/SITEs
        for line in fileinput.input(file_resp):
            ip_list.append(line)

    # Define a certain range of IPs
    elif method_resp == "range":
        print "Defining a range..."

    # Define one or more IPs individually
    elif method_resp == "custom":
        print 'Define using /32 IP Addresses'
        answer = ""
        while( answer != 'x' ):
            answer = getInputAnswer('Enter an ip address (x) to exit')
            if( answer != 'x'):
                ip_list.append(answer)

    # Print the IPs that will be used
    loop = 1;
    for my_ip in ip_list:
        print 'IP' + str(loop) + '-> ' + my_ip
        loop=loop + 1

    return ip_list

# Converts listDict to CSV file
def listDictCSV(myListDict, filePathName, keys):
    addKeys = True
    if (os.path.isfile(filePathName)):
        addKeys = False
    try:
        f = open(filePathName, 'a')
    except Exception as err:
        print "Failure opening file in append mode - ERROR: {0}".format(err)
        print "Be sure {0} isn't open in another program.".format(filePathName)
    else:
        if addKeys:
            #Write all the headings in the CSV
            for akey in keys[:-1]:							# Runs for every element, except the last
                f.write(akey + ",")							# Writes most elements
            f.write(keys[-1])								# Writes last element
            f.write("\n")

        for part in myListDict:
            for bkey in keys[:-1]:
                #print "Key: " + bkey + "  Value: " + str(part[bkey])
                f.write(str(part[bkey]) + ",")
            f.write(str(part[keys[-1]]))
            f.write("\n")
        f.close()
        print "\nCompleted appending to CSV."

# Converts CSV file to listDict
def csvListDict(fileName):
    myListDict = []
    try:
        with open(fileName) as myfile:
            firstline = True
            for line in myfile:
                if firstline:
                    mykeys = "".join(line.split()).split(',')
                    firstline = False
                else:
                    values = "".join(line.split()).split(',')
                    a.append({mykeys[n]:values[n] for n in range(0,len(mykeys))})
    except Exception as err:
        print "Failure converting CSV to listDict - ERROR: {0}".format(err)
    return myListDict

# Gets a target code
def getCode(device, mypath):
    tar_code = ""

    # Does not have a target code, let's ask for one
    print("\n" + "*"*10)
    print("Hostname: " + device.hostname)
    print("IP: " + device.ip)
    print("Model: " + device.model)
    print("Current Code: " + device.curr_code)

    fileList = getFileList(mypath)
    if fileList:
        tar_code = getOptionAnswer("Choose an image", fileList)
    else:
        print("No images available.")
    print("*"*10 + "\n")

    return tar_code

# Analyze listDict and create statistics (Upgrade)
def tabulateUpgradeResults(listDict):
    statusDict = {'success_rebooted': [],'success_not_rebooted': [], 'connect_fails': [], 'software_install_fails': [], 'total_devices': 0}

    for mydict in listDict:
        if mydict['Connected'] == 'Y' and mydict['OS_installed'] == 'Y':
            if mydict['Rebooted'] == 'Y':
                statusDict['success_rebooted'].append(mydict['IP'])
            else:
                statusDict['success_not_rebooted'].append(mydict['IP'])
        elif mydict['Connected'] == 'Y' and mydict['OS_installed'] == 'N':
            statusDict['software_install_fails'].append(mydict['IP'])
        elif mydict['Connected'] == 'N':
            statusDict['connect_fails'].append(mydict['IP'])
        else:
            print("Error: Uncaptured Result")
        # Every device increments this total
        statusDict['total_devices'] += 1

    return statusDict

# Analyze listDict and create statistics (Reboot)
def tabulateRebootResults(listDict):
    statusDict = {'rebooted': [], 'not_rebooted': [], 'connect_fails': [], 'total_devices': 0}

    for mydict in listDict:
        if mydict['Connected'] == 'Y':
            if mydict['Rebooted'] == 'Y':
                statusDict['rebooted'].append(mydict['IP'])
            else:
                statusDict['not_rebooted'].append(mydict['IP'])
        elif mydict['Connected'] == 'N':
            statusDict['connect_fails'].append(mydict['IP'])
        else:
            print("Error: Uncaptured Result")
        # Every device increments this total
        statusDict['total_devices'] += 1

    return statusDict

# Get fact
def get_fact(ip, username, password, fact):
    """ Purpose: For collecting a single fact from the target system. The 'fact' must be one of the predefined ones.
        Examples:
            model, version, hostname, serialnumber,
            switch_style, last_reboot_reason, uptime,
            personality
        Parameters:
    """
    dev = Device(ip, user=username, password=password)
    try:
        dev.open()
    except Exception as err:
        print("Unable to open connection to: {0} | ERROR: {1}").format(ip, err)
    else:
        myfact = dev.facts[fact]
        dev.close()
        return myfact

# Run a single non-edit command and get the output returned
def op_command(ip, host_name, command, username, password, port=22):
    """ Purpose: For the -c flag, this function is called. It will connect to a device, run the single specified command, and return the output.
                 Paramiko is used instead of ncclient so we can pipe the command output just like on the CLI.
        Parameters:
            ip          -   String containing the IP of the remote device, used for logging purposes.
            host_name   -   The device host-name for output purposes.
            commands    -   String containing the command to be sent to the device.
            username    -   Username used to log into the device
            password    -   Password is needed because we are using paramiko for this.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    device = '*' * 80 + '\n[%s at %s] - Command: %s\n' % (host_name, ip, command)
    command = command.strip() + ' | no-more\n'
    output = ''
    try:
        ssh.connect(ip, port=port, username=username, password=password)
        stdin, stdout, stderr = ssh.exec_command(command=command, timeout=900)
        stdin.close()
        # read normal output
        while not stdout.channel.exit_status_ready():
            output += stdout.read()
        stdout.close()
        # read errors
        while not stderr.channel.exit_status_ready():
            output += stderr.read()
        stderr.close()
        output = '%s \n %s' % (device, output)
        return output
    except paramiko.AuthenticationException:
        output = '*' * 45 + '\n\nBad username or password for device: %s\n' % ip
        return output

# Run multiple non-edit commands from a file
def op_multiple_commands(ip, host_name, multiple_commands, username, password, port=22):
    """ Purpose: For the -mc flag, this function is called. It will connect to a device, run the list of specified commands, and return the output.
        Parameters:
            connection          -   The NCClient manager connection to the remote device.
            ip                  -   String containing the IP of the remote device, used for logging purposes.
            host_name           -   The device host-name for output purposes.
            multiple_commands   -   The file containing the list of commands.
            commands            -   String containing the command to be sent to the device.
            username            -   Username used to log into the device
    """
    output = ''
    command_file = open(multiple_commands, 'r')
    for command in command_file:
        command = command.rstrip()
        output += op_command(ip, host_name, command, username, password, port)
    return output


def set_command(connection, ip, host_name, commands):
    """ Purpose: This is the function for the -s or -sl flags. it will send set command(s) to a device, and commit the change.
        Parameters:
            connection  -   The NCClient manager connection to the remote device.
            ip          -   String containing the IP of the remote device, used for logging purposes.
            host_name   -   The device host-name for output purposes.
            commands    -   String containing the set command to be sent to the device, or a list of strings of multiple set commands.
                            Either way, the device will respond accordingly, and only one commit will take place.
    """
    dot = "."
    print "*" * 80
    print "Applying configuration on {0} ".format(ip),
    print dot,
    try:
        connection.lock()
    except Exception as err:
        print "{0}: Unable to Lock configuration : {1}".format(ip, err)
        return

    print dot,
    try:
        connection.load_configuration(action='set', config=commands)
    except Exception as err:
        print "{0}: Unable to Load the configuration : {1}".format(ip, err)
        print "{0}: Unlocking the configuration".format(ip)
        try:
            connection.unlock()
        except Exception as err:
            print "{0}: Unable to Unlock the configuration : {1}".format(ip, err)
        connection.close_session()
        return

    print dot,
    try:
        connection.commit()
    except Exception as err:
        print "{0}: Commit fails : {1}".format(ip, err)
        output = 'Commit complete on %s at %s' % (host_name, ip)
        return

    print dot,
    try:
        connection.unlock()
    except Exception as err:
        print "{0}: Unable to Unlock the configuration : {1}".format(ip, err)
        connection.close_session()
        return

    connection.close_session()
    print "Successfully Completed Configuration"


def set_list(connection, ip, host_name, file_name):
    """ Purpose: The -sl flag will trigger this function, which is used to parse a list of set commands in a file, and prepare them for sending.
                 It will then call the set_command() function to actually send the list to the device and commit the changes.
        Parameters:
            connection  -   The NCClient manager connection to the remote device.
            ip          -   String containing the IP of the remote device, used for logging purposes.
            host_name   -   The device host-name for output purposes.
            set_list_file_name    -   The filepath to the file containing the set commands, each on a separate line.
    """
    command_list = []
    command_file = open(file_name, 'r')
    for c in command_file:
        command_list.append(c)
    output = set_command(connection, ip, host_name, command_list)
    return output


def run(ip, username, password, port, command_list):
    """ Purpose: To open an NCClient manager session to the device, and run the appropriate function against the device.
        Parameters:
            ip          -   String of the IP of the device, to open the connection, and for logging purposes.
            username    -   The string username used to connect to the device.
            password    -   The string password used to connect to the device.
    """
    output = ''
    try:
        #print "{0}: Establishing connection...".format(ip)
        connection = manager.connect(host=ip,
                                     port=port,
                                     username=username,
                                     password=password,
                                     timeout=15,
                                     device_params={'name':'junos'},
                                     hostkey_verify=False)
        connection.timeout = 300
    except errors.SSHError:
        output = '*' * 45 + '\n\nUnable to connect to device: %s on port: %s\n' % (ip, port)
        print output
    except errors.AuthenticationError:
        output = '*' * 45 + '\n\nBad username or password for device: %s\n' % ip
        print output
    else:
        software_info = connection.get_software_information(format='xml')
        host_name = software_info.xpath('//software-information/host-name')[0].text
        output = set_command(connection, ip, host_name, command_list)


def load_with_pyez(format_opt, merge_opt, overwrite_opt, conf_file, log_file, ip, username, password):
    """ Purpose: Perform the actual loading of the config file. Catch any errors.
    """
    dot = "."

    output += "*" * 80
    output += 'Applying configuration on {0} '.format(ip)
    print dot,
    try:
        dev = Device(ip, user=username, password=password)
        dev.open()
    except ConnectError as err:
        do_log("{0}: Cannot connect to device : {1}".format(ip, err))
        return
    dev.bind(cu=Config)


    #print("Try locking the configuration...")
    print dot,
    try:
        dev.cu.lock()
    except LockError as err:
        do_log("{0}: Unable to lock configuration : {1}".format(ip, err))
        dev.close()
        return

    #print("Try loading configuration changes...")
    print dot,
    try:
        dev.cu.load(path=conf_file, merge=merge_opt, overwrite=overwrite_opt, format=format_opt)
    except (ConfigLoadError, Exception) as err:
        do_log("{0}: Unable to load configuration changes : {1}".format(ip, err))
        do_log("{0}: Unlocking the configuration".format(ip))
        try:
            dev.cu.unlock()
        except UnlockError as err:
            do_log("{0}: Unable to unlock configuration : {1}".format(ip, err))
        dev.close()
        return

    #print("Try committing the configuration...")
    print dot,
    try:
        dev.cu.commit()
    except CommitError as err:
        do_log("{0}: Unable to commit configuration : {1}".format(ip, err))
        do_log("{0}: Unlocking the configuration".format(ip))
        try:
            dev.cu.unlock()
        except UnlockError as err:
            do_log("{0}: Unable to unlock configuration : {1}".format(ip, err))
        dev.close()
        return

    #print("Try Unlocking the configuration...")
    print dot
    try:
        dev.cu.unlock()
    except UnlockError as err:
        do_log("{0}: Unable to unlock configuration : {1}".format(ip, err))
        dev.close()
        return

    # End the NETCONF session and close the connection
    dev.close()
    do_log("Successfully Completed Configuration Change")


def screen_and_log(output, log_file):
    myfile = open(log_file, 'a')
    print("--> " + output)