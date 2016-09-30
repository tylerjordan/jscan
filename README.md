# JUPGRADE - Juniper Upgrade Script
# Author: Tyler Jordan

The purpose of this python script is to perform upgrades for one or more Juniper devices. The user can specify devices using the "Add Device" option or creating a CSV file with the IP and target OS .tgz file. The user will need a valid username/password that has Netconf SSH access to device(s).

Step 1: Start jscan script. The script takes an argument for a user, this will be the username to log into the Juniper devices. 
      > python jscan.py -u <username>    ie. python jscan.py -u admin

Step 2: User will be prompted for a username password. Enter the corresponding password for the username.

Step 3: Select the devices to upgrade using "Add Device" or "Load Devices" by using the CSV file to specify multiple devices.

Step 4: Select "Bulk Upgrade" to start process to upgrade devices

Step 5: (Optional) Select "Bulk Reboot" to upgrade multiple deivces


# Rack Meunu Options:

1. Show Devices -> Display information about the selected devices

2. Refersh Devices -> Refresh information on the selected devices (ie. after upgrading to verify software upgrade)

3. Add Device -> Add a device to the "rack", these will be the "selected devices" mentioned above. Enter the IP of the device when prompted. This is used for adding a single device or if user just wants to upgrade a few devices. (optional)

4. Load Devices -> Used for adding multiple devices using a CSV file containing IPs and target code (optional)

5. Bulk Upgrade -> Select this to start the upgrade procedure on selected devices. Each device to be upgraded must have an target code specified. This process will ask for any devices where this was not specified. User will be asked for reboot preferences. Select "Reboot all devices after upgrade (to complete upgrade), "Do not reboot ANY devices", and "Ask for each device after upgrading". 

6. Bulk Reboot -> Select this to perform a reboot on selected devices.

7. Quit -> Exit the script
