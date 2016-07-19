# File: utility.py
# Author: Tyler Jordan
# Modified: 7/19/2016
# Purpose: Assist CBP engineers with Juniper configuration tasks

import sys, re
import fileinput
import glob
import code

from os import listdir
from os.path import isfile, join

#--------------------------------------
# ANSWER METHODS
#--------------------------------------
# Method for asking a question that has a single answer, returns answer
def getOptionAnswer(question, options):
	answer = ""
	loop = 0;
	while not answer:
		print question + '?:\n'
		for option in options:
			loop += 1
			print '[' + str(loop) + '] -> ' + option
		answer = raw_input('Your Selection: ')
		if answer >= "1" and answer <= str(loop):
			index = int(answer) - 1
			return options[index]
		else:
			print "Bad Selection"
			answer = ""
			
# Method for asking a question that has a single answer, returns answer index
def getOptionAnswerIndex(question, options):
	answer = ""
	loop = 0;
	while not answer:
		print question + '?:\n'
		for option in options:
			loop += 1
			print '[' + str(loop) + '] -> ' + option
		answer = raw_input('Your Selection: ')
		if answer >= "1" and answer <= str(loop):
			return index
		else:
			print "Bad Selection"
			answer = ""

# Method for asking a question, with multiple options, and multiple answers
def getMultiAnswer(question, options):
	answer = ""
	answers = {}
	loop = 0;
	while not answer:
		print question + '?:\n'
		for option in options:
			loop += 1
			print '[' + str(loop) + '] -> ' + option
		print '[x] -> Submit Selections'
		answer = raw_input('Your Selection: ')
		if answer >= "1" and answer <= str(loop):
			index = int(answer) - 1
			answers.append(options[index])
		elif answer == "x":
			return answers
		else:
			print "Bad Selection"
			answer = ""

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

# Return list of files from a directory
def getFileList(mypath):
	fileList = []
	try:
		for afile in listdir(mypath):
			if isfile(join(mypath,afile)):
				fileList.append(afile)
	except:
		print "Error accessing directory: " + mypath
		
	return fileList

# Method for requesting IP address target
def getTarget():
	print 64*"="
	print "= Scan Menu                                                    ="
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
def listDictCSV(myListDict, fileName, keys):
	
	try:
		f = open(fileName, 'w')
	except:
		print "Failure opening file in write mode"
	
	# Write all the headings in the CSV
	for akey in keys[:-1]:							# Runs for every element, except the last
		f.write(akey + ",")							# Writes most elements
	f.write(keys[-1])								# Writes last element
	f.write("\n")
	
	for part in myListDict:
		for bkey in keys[:-1]:
			# print "Key: " + key + "  Value: " + part[key]
			f.write(part[bkey] + ",")
		f.write(part[keys[-1]])
		f.write("\n")
	f.close()
	print "Completed writing commands."

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
	except:
		print "Failure converting CSV to listDict"
	return myListDict

# Creates a list of valid files based off regex match
def jinstallFilter(filedir, model):
	fileList = getFileList(filedir)
	filterList = []
	for oneFile in fileList:
		m = re.match("jinstall(\d{2}\-|\-)\w{2,5}\-\d{1,5}.*", oneFile)
		if m:
			fullFile = oneFile.split("-")
			fileModel = fullFile[1].upper() + fullFile[2]
			devicemod = model.split("-")
			deviceModel = devicemod[0]
			print("DeviceModel:" + deviceModel[0:4] + " FileModel:" + fileModel[0:4])
			if fileModel[0:4] == deviceModel[0:4]:
				filterList.append(oneFile)
		else:
			filterList.append(oneFile)
	return filterList
