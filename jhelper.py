import paramiko  # https://github.com/paramiko/paramiko for -c -mc -put -get
import argparse  # for parsing command line arguments.
import getpass  # for retrieving password input from the user without echoing back what they are typing.
from ncclient import manager  # https://github.com/ncclient/ncclient
from ncclient.transport import errors
from multiprocessing import Pool  # For running on multiple devices at the same time.

__copyright__ = "Copyright 2015 Clay Hoy"
__version__ = "0.1.2"
__email__ = "choy@juniper.net"

""" When using -s to change the root password, you need to use the encrypted format 
put a '/' before every '$'.
"""

"""
To do:

- need to look into what how to report a problem when an exception is hit during multiprocessing.
    Currently if an exception is hit, that device is skipped with no indication that it was skipped.
    I would like some output saying "device x was skipped due to a problem."
    A temp fix is in place for -info

"""

# Optional parameters: If you don't enter a username and password, it will ask for them.
parser = argparse.ArgumentParser(description='jhelper is used to interact with multiple Juniper devices at once.  '
                                             'To request a feature, please contact Clay: choy@juniper.net')
parser.add_argument("-u", dest='username', metavar='<username>', type=str, help="Username")
parser.add_argument("-p", dest='password', metavar='<password>', type=str, help="Password")
parser.add_argument("-port", dest='port', metavar='<port>', default=22, type=int, help="SSH port to use, default = 22")
parser.add_argument("-w", dest='write', metavar='<destination>', type=str, help="Write output to a file.")
parser.add_argument("-info", dest='info', action='store_true', help="Get device information.")
parser.add_argument("-hc", dest="health_check", action="store_true",
                    help="CPU/Mem, alarms, environment, RE info and last few log entries.")
parser.add_argument("-e", dest='int_error', action='store_true', help='Check all interfaces for errors.') 
parser.add_argument("-clean", dest='clean_up', action='store_true', help='Checks for unused firewall filters '
                                                                         'and policy-statements.')

# IP vs IP list: One of the two is required, they are mutually exclusive.
group1 = parser.add_mutually_exclusive_group()
group1.add_argument("-ip", dest='ip', metavar='<ip address>', type=str, help="Device IP address.")
group1.add_argument("-ipl", dest='iplist', metavar='<source>', help="List of device IPs in a text file.")

# Script functions: Must select one and only one.
group2 = parser.add_mutually_exclusive_group()
group2.add_argument("-c", dest='command', metavar='<command>', type=str, help="Send a single command to device(s).")
group2.add_argument("-get", dest='get', metavar=('<source>', '<destination>'), nargs=2,
                    type=str, help="Get a file from device(s).")
group2.add_argument("-mc", dest='multiple_commands', metavar='<source>', type=str,
                    help="Send multiple commands to device(s).")
group2.add_argument("-put", dest='put', metavar=('<source>', '<destination>'), nargs=2, type=str,
                    help="Push a file to device(s).")
group2.add_argument("-s", dest='set_single', metavar='<command>', type=str,
                    help="Send a single set/delete command to device(s).")
group2.add_argument("-sl", dest='set_list', metavar='<source>', type=str,
                    help="Send a file of set/delete commands to device(s).")


def fw_and_policy_clean_up(ip, host_name, configuration):
    """ Purpose: This is the function called by using the -hc flag on the command line.
                 It grabs the cpu/mem usage, system/chassis alarms, top 7 processes.

                 "Firewall filter check - No known issues."
                 "Policy statement check - If another variable's name is an exact match to a policy name,
                 that can create a false policy-in-use match."

        Parameters:
            connection  -  This is the ncclient manager connection to the remote device.
            ip          -  String containing the IP of the remote device, used for logging purposes.
            host_name   -  The device host-name for output purposes.

    """
    import re
    output = "*" * 45 + '\nDevice: %s at %s\n' % (host_name, ip)
    output += '\n ############## \n\n'

    # All variables used:
    allconfig = []
    policy = []
    firewall = []
    fwf = ''
    fw_used = 0
    fw_unused_count = 0
    fwf_count = 0
    ps = ''
    ps_used = 0
    ps_unused_count = 0
    ps_count = 0
    print1 = 0
    print2 = 0

    # Sort configuration into sections, firewall filters from all families, policy-statements, and everything else.
    configuration = configuration.split('\n')
    for line in configuration:
        if 'set firewall ' in line:
            firewall.append(line)
        elif 'set policy-options policy-statement ' in line:
            policy.append(line)
        else:
            allconfig.append(line)

    # Find firewall filters and check the configuration to see if they are applied anywhere.
    for cmd in firewall:
        if 'filter' in cmd:
            cmd1 = cmd.split(' ')
            num = cmd1.index('filter')
            if cmd1[num+1] == fwf:
                pass
            else:
                fwf_count += 1
                fwf = cmd1[num+1]
                fw_filter_match2 = ' input ' + fwf
                fw_filter_match3 = ' output ' + fwf
                match4 = re.compile(".* input-list .*" + fwf)
                match5 = re.compile(".* output-list .*" + fwf)
                for fwcmd in allconfig:
                    results = match4.match(fwcmd)
                    results2 = match5.match(fwcmd)
                    if fw_filter_match2 in fwcmd:
                        fw_used = 1
                    elif fw_filter_match3 in fwcmd:
                        fw_used = 1
                    elif results:
                        fw_used = 1
                    elif results2:
                        fw_used = 1
                if fw_used == 0:
                    word_after_fwf = cmd.split(' ')[cmd1.index(fwf)+1]
                    cmd2 = cmd.split(word_after_fwf)
                    output += cmd2[0].replace('set', 'delete', 1) + '\n'
                    fw_unused_count += 1
                    print1 = 1
                fw_used = 0

    if print1 == 0:
        output += 'All firewall filters are being used.\n'

    output += '\n ############## \n\n'

    # Find policy-statement names and check configuration to see if they are applied anywhere.
    for cmd in policy:
        cmd1 = cmd.split(' ')

        # If the policy-statement name is the same as the last one then skip it.  Else check the config for its use.
        if cmd1[3] == ps:
            pass
        else:
            ps_count += 1
            ps = cmd1[3]

            # Looks for either the end of the line or a space after the end of the policy name.
            command = re.compile(".* " + ps + "$")
            command2 = re.compile(".* " + ps + " ")
            for cmd_int in allconfig:
                result = command.match(cmd_int)
                result2 = command2.match(cmd_int)
                if result:
                    ps_used = 1
                elif result2:
                    ps_used = 1
            if ps_used == 0:
                output += 'delete policy-options policy-statement %s\n' % ps
                ps_unused_count += 1
                print2 = 1
            ps_used = 0

    if print2 == 0:
        output += 'All policy statements are being used.\n'

    # Print stats
    output += '\n ############## \n'
    output += 'Total number of firewall filters: %s\n' % fwf_count
    output += 'Total number of unused firewall filters: %s\n' % fw_unused_count
    output += 'Total number of policy statements: %s\n' % ps_count
    output += 'Total number of unused policy statements: %s\n' % ps_unused_count

    return output


def health_check(connection, ip, host_name):
    """ Purpose: This is the function called by using the -hc flag on the command line.
                 It grabs the cpu/mem usage, system/chassis alarms, top 7 processes.
        Parameters:
            connection  -  This is the ncclient manager connection to the remote device.
            ip          -  String containing the IP of the remote device, used for logging purposes.
            host_name   -  The device host-name for output purposes.
    """
    output = "*" * 45 + '\nDevice: %s at %s\n' % (host_name, ip)

    # Check for chassis alarms and add them to the output.
    chassis_alarms = connection.command(command="show chassis alarms", format='xml')
    output += '\nChassis alarms:\n'
    if not chassis_alarms.xpath('//alarm-detail'):
        output += 'No alarms currently active.\n'
    else:
        for i in chassis_alarms.xpath('//alarm-detail'):
            output += (i.xpath('alarm-time')[0].text.strip() + '\t  ' + i.xpath('alarm-class')[0].text.strip() +
                       '\t  ' + i.xpath('alarm-description')[0].text.strip() + '\n')

    # Check for system alarms and add them to the output.
    system_alarms = connection.command(command="show system alarms", format='xml')
    output += '\nSystem alarms:\n'
    if not system_alarms.xpath('//alarm-detail'):
        output += 'No alarms currently active.\n'
    else:
        for i in system_alarms.xpath('//alarm-detail'):
            output += (i.xpath('alarm-time')[0].text.strip() + '\t  ' + i.xpath('alarm-class')[0].text.strip() +
                       '\t  ' + i.xpath('alarm-description')[0].text.strip() + '\n')
    
    # Get show chassis environment
    output += '\nChassis environment:'
    environment = connection.command(command="show chassis environment", format='text')
    # This is necessary for vMX devices:
    try:
        output += environment.xpath('//output')[0].text
    except:
        output += '\nNo output received - normal for vMX.\n'

    # Get show chassis routing-engine
    routing_engine = connection.command(command="show chassis routing-engine", format='text')
    output += routing_engine.xpath('//output')[0].text

    # Get the processes and add the top 7 to the output. 
    output += '\nTop 7 processes:\n'
    processes = connection.command(command="show system processes extensive", format='xml')
    processes = processes.xpath('output')[0].text.split('\n')
    for line_number in range(8, 16):
        output += processes[line_number] + '\n'
    return output
    # the last 10 log messages are also shown, but this is done under junos_run and not here.


def information(connection, ip, software_info, host_name):
    """ Purpose: This is the function called when using -info.
                 It is grabs the model, running version, and serial number of the device.
        Parameters:
            connection    -  This is the ncclient manager connection to the remote device.
            ip            -  String containing the IP of the remote device, used for logging purposes.
            software_info -  A "show version" aka "get-software-information".
            host_name     -  The device host-name for output purposes.
    """
    try:
        model = software_info.xpath('//software-information/product-model')[0].text
        junos = software_info.xpath('//software-information/junos-version')[0].text
        chassis_inventory = connection.get_chassis_inventory(format='xml')
        serial_number = chassis_inventory.xpath('//chassis-inventory/chassis/serial-number')[0].text
        return '*' * 45 + '\nHost-name: %s \nAccessed via: %s \nModel: %s \nJunos: ' \
                          '%s \nSerial Number: %s\n' % (host_name, ip, model, junos, serial_number)
    except:
        return '*' * 45 + '\nHost-name: %s \nAccessed via: %s \nDevice was reachable, ' \
                          'the information was not found.' % (host_name, ip)


def interface_errors(connection, ip, host_name):
    """ Purpose: This function is called when using -e. It will let the user know if there are any interfaces with
                 errors, and what those interfaces are.

        Parameters:
            connection  -   The NCClient manager connection to the remote device.
            ip          -   String containing the IP of the remote device, used for logging purposes.
            host_name   -   The device host-name for output purposes.
    """
    int_list = []  # used to store the list of interfaces with errors.
    error_counter = 0  # used to count the number of errors found on a device.
    int_list.append('*' * 45 + '\n%s at %s\n' % (host_name, ip))  # append a header row to the output.
    result_xml = connection.command(command='show interfaces extensive', format='xml')
    result_xml = result_xml.xpath('//physical-interface')
    for i in result_xml:
        int_name = i.xpath('name')[0].text[1:-1]
        if ('ge' or 'fe' or 'ae' or 'xe' or 'so' or 'et' or 'vlan' or 'lo0' or 'irb' or 'st0') in int_name:
            if 'up' in i.xpath('oper-status')[0].text:
                error_list = {}
                # Grab the input errors
                in_err = i.xpath('input-error-list')[0]
                # Loop through all subelements of input-error-list, storing them in a dictionary
                # of { 'tag' : 'value' } pairs.
                for x in range(len(in_err)):
                    error_list[in_err[x].tag] = int(in_err[x].text.strip())
                    # Grab the output errors
                out_err = i.xpath('output-error-list')[0]
                for x in range(len(out_err)):
                    error_list[out_err[x].tag] = int(out_err[x].text.strip())
                notfound = False
                # Loop through and check for errors
                while notfound is False:
                    # key is the xml tag name for the errors. value is the integer for that counter.
                    for key, value in error_list.iteritems():
                        if key == 'carrier-transitions':
                            if value > 50:
                                int_list.append("%s has greater than 50 flaps" % int_name)
                                error_counter += 1
                        elif value > 0:
                            int_list.append("%s has %s." % (int_name, key))
                            error_counter += 1
                    notfound = True
    if error_counter == 0:
        int_list.append('No interface errors were detected on this device.')
    output = '\n'.join(int_list)
    return output


def op_command(ip, host_name, command, username, password, port):
    """ Purpose: For the -c flag, this function is called. It will connect to a device, run the single specified
                 command, and return the output.  Paramiko is used instead of ncclient so we can pipe the command
                 output just like on the CLI.
        Parameters:
            ip          -   String containing the IP of the remote device, used for logging purposes.
            host_name   -   The device host-name for output purposes.
            commands    -   String containing the command to be sent to the device.
            username    -   Username used to log into the device
            password    -   Password is needed because we are using paramiko for this.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    device = '*' * 45 + '\nResults from %s at %s' % (host_name, ip)
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


def op_multiple_commands(ip, host_name, multiple_commands, username, password, port):
    """ Purpose: For the -mc flag, this function is called. It will connect to a device, run the list of specified
        commands, and return the output.

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


def run(ip, username, password, port):
    """ Purpose: To open an NCClient manager session to the device, and run the appropriate function against the device.
        Parameters:
            ip          -   String of the IP of the device, to open the connection, and for logging purposes.
            username    -   The string username used to connect to the device.
            password    -   The string password used to connect to the device.
    """
    try:
        connection = manager.connect(host=ip,
                                     port=port,
                                     username=username,
                                     password=password,
                                     timeout=15,
                                     device_params={'name': 'junos'},
                                     hostkey_verify=False)
        connection.timeout = 300
    except errors.SSHError:
        output = '*' * 45 + '\n\nUnable to connect to device: %s on port: %s\n' % (ip, port)
    except errors.AuthenticationError:
        output = '*' * 45 + '\n\nBad username or password for device: %s\n' % ip
    else:
        output = ''
        software_info = connection.get_software_information(format='xml')
        host_name = software_info.xpath('//software-information/host-name')[0].text
        # -c and -mc use paramiko so sending connection is not necessary
        if args.command:
            output += op_command(ip, host_name, args.command, username, password, port)
        elif args.multiple_commands:
            output += op_multiple_commands(ip, host_name, args.multiple_commands, username, password, port)
        elif args.set_single:
            output += set_command(connection, ip, host_name, args.set_single)
        elif args.set_list:
            output += set_list(connection, ip, host_name, args.set_list)
        elif args.get or args.put:
            output += scp_file(scp_source, scp_dest, ip, host_name, username, password, port)
        if args.int_error:
            output += interface_errors(connection, ip, host_name)
        if args.info:
            output += information(connection, ip, software_info, host_name)
        if args.health_check:
            output += health_check(connection, ip, host_name)
            # Also grab the last 10 log messages
            command = 'show log messages | last 10'
            output_unfiltered = op_command(ip, host_name, command, username, password, port)
            output_unfiltered = output_unfiltered.splitlines(True)
            output += '\n'
            for line in range(2, len(output_unfiltered)):
                output += output_unfiltered[line]
        if args.clean_up:
            configuration = op_command(ip, host_name, 'show configuration | display set | no-more',
                                       username, password, port)
            output += fw_and_policy_clean_up(ip, host_name, configuration)
    return output


def scp_file(scp_source, scp_dest, ip, host_name, username, password, port):
    """ Purpose: This function is called by using -get or -put flag on the command line. 
                 It is used to scp a file from the specified source and destinations
        Parameters:
            scp_source  -   source file for the SCP transaction.
            scp_dest    -   destination file for the SCP transaction.
            ip          -   the remote IP address for the SCP transaction.
            host_name   -   The device host-name for output purposes.
            username    -   the username for the remote device.
            password    -   the password for the remote device.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, port=port, username=username, password=password)
    scp = SCPClient(ssh.get_transport())
    try:
        if args.get:
            scp.get(scp_source, scp_dest)
            return 'Received %s from %s at %s' % (scp_source, host_name, ip)
        else:
            scp.put(scp_source, scp_dest)
            return 'Put %s on %s at %s%s' % (scp_source, host_name, ip, scp_dest)
    except:
        return 'Undefined error received. Check username, password and permissions.'


def set_command(connection, ip, host_name, commands):
    """ Purpose: This is the function for the -s or -sl flags. it will send set command(s) to a device,
        and commit the change.

        Parameters:
            connection  -   The NCClient manager connection to the remote device.
            ip          -   String containing the IP of the remote device, used for logging purposes.
            host_name   -   The device host-name for output purposes.
            commands    -   String containing the set command to be sent to the device, or a list of strings of
                            multiple set commands.  Either way, the device will respond accordingly, and only one
                            commit will take place.
    """
    try:
        connection.lock()
        connection.load_configuration(action='set', config=commands)
        connection.commit()
        output = 'Commit complete on %s at %s' % (host_name, ip)
        connection.unlock()
        connection.close_session()
        return output
    except:
        output = 'Commit failed on %s at %s' % (host_name, ip)
        return output


def set_list(connection, ip, host_name, set_list_file_name):
    """ Purpose: The -sl flag will trigger this function, which is used to parse a list of set commands in a file,
                 and prepare them for sending.  It will then call the set_command() function to actually send the
                 list to the device and commit the changes.
        Parameters:
            connection  -   The NCClient manager connection to the remote device.
            ip          -   String containing the IP of the remote device, used for logging purposes.
            host_name   -   The device host-name for output purposes.
            set_list_file_name    -   The filepath to the file containing the set commands, each on a separate line.
    """
    command_list = []
    command_file = open(set_list_file_name, 'r')
    for c in command_file:
        command_list.append(c)
    output = set_command(connection, ip, host_name, command_list)
    return output


def write_to_file(output):
    """ Purpose: This function is called to either print the output to the user, or write it to a file if -w is called.
        Parameters:
            output  -  String or list of strings containing all the output gathered throughout the script.
    """
    if args.write:
        output_file.write('%s \n' % output)
    else:
        print output


##########################
# Start of script proper #
##########################
if __name__ == '__main__':
    # Verify requirements.
    args = parser.parse_args()

    if args.get or args.put:
        from scp import SCPClient
        if args.get:
            scp_source = args.get[0]
            scp_dest = args.get[1]
        else:
            scp_source = args.put[0]
            scp_dest = args.put[1]

    if not (args.ip or args.iplist):
        parser.error('A target IP must be specified.\n Use -h for help.')
    if not (args.command or args.int_error or args.get or args.info or args.put or args.set_single or args.set_list or
            args.health_check or args.multiple_commands or args.clean_up):
        parser.error('A command must be called: [-c | -e | -get | -hc | '
                     '-info | -mc | -put | -ss | -sl | -clean]\n Use -h for help.')
    if not args.username:
        args.username = raw_input("Username: ")
    if not args.password:
        args.password = getpass.getpass()

    # Open the output file if -w was given.
    if args.write:
        output_file = open(args.write, 'w')

    # -ip calls a single device, -ipl will enact multiprocessing to speed up the job.
    if args.ip:
        output = run(args.ip, args.username, args.password, args.port)
        write_to_file(output)
    # Modified for CBP
    elif args.iplist:
        iplist = open((".\\lists\\" + args.iplist), 'r')
        #mp_pool = Pool()
        #for ip in iplist:
            #ip = ip.strip()
        firstline = True
        for line in iplist:
            if firstline:
                firstline = False
                continue
            mylist = line.split(',')
            #print("IP: {0}".format(mylist[0]))
            output = run(mylist[0], args.username, args.password, args.port)
            write_to_file(output)
            #mp_pool.apply_async(run, args=(ip, args.username, args.password, args.port, ), callback=write_to_file)
        #mp_pool.close()
        #mp_pool.join()
    
