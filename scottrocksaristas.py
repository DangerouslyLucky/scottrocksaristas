#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Scott Cuthbert

This script is designed for Arista switches.
Attempting to recreate the functionality of 'ciscocmd7k' without using expect

Allows input of a single command or multiple commands (via textfile) to be
run against a single switch or multiple switches (via textfile)

"""

import pyeapi
import argparse
import getpass
import ssl


# TODO figure out why I need this or things go bonkers
ssl._create_default_https_context = ssl._create_unverified_context

global commandType      # how to execute the command: show/enable/config
commandType = 'show'
global saveRun          # --save flag from parser.
saveRun = False
global ignoreChars      # lines that start with these get removed from commands
ignoreChars = ["!", "#"]


def main():

    # get arguments from parser
    args = parser()
    if args.grabrun:
        global saveRun
        saveRun = True

    # define variables, even if they werent parser provided
    username = get_username(args.username)
    password = get_password(args.password)
    switches = get_switch_list(args.multiswitch, args.switch)
    commands = get_commands_list(args.commandsfile, args.command)
    set_command_type(commands)
    list_element_removal(commands, ignoreChars)

    # the main squeeze
    scottrocks(switches, commands, username, password)

    # Scott Rocks // End of Script


# where the magic happens
def scottrocks(switchList, commandsList, user, password):

    for switch in switchList:

        # list that fills with info from ran commands, clears after each switch
        outputInfo = []
        outputInfo.append("Processing switch " + switch + "\n")

        try:
            # connect
            node = switch_connect(user, password, switch)

            # grab hostname
            host_name = run_command(node, ["show hostname"])
            for item in host_name:
                outputInfo.append(item)

            # save running config before --save
            if saveRun:
                outputInfo.append(grab_run(node, "before"))

            # finally run the commands
            cmdOutput = run_command(node, commandsList)
            for item in cmdOutput:
                outputInfo.append(item)

            # save running config after --save
            if saveRun:
                outputInfo.append(grab_run(node, "after"))

        # TODO add better error checking here
        except pyeapi.eapilib.ConnectionError as err:
            outputInfo.append("WE ENCOUNTERED A CONNECTION ISSUE")
            outputInfo.append("Error command: %s" % err.command)
            outputInfo.append("Error message: %s" % err.message)
        except Exception as msg:
            outputInfo.append("Either could not open connection to " + switch +
                              " or could not run command\n")
            outputInfo.append("Exception msg = %s " % msg)

        write_output(outputInfo)


def list_element_removal(fullList, element):

    print("Cleaning up list of commands.\nRemoving comments.")
    fullList[:] = [item for item in fullList if item[:1] not in element]

    return fullList


# TODO make this funciton return more human readable output
def config_command(switch, commands):

    results = switch.config(commands)

    return results


def enable_command(switch, commands):

    results = switch.enable([commands], encoding='text',
                            strict=False, send_enable=True)

    return results


def show_command(switch, command):

    command = command[0]

    messy_command = switch.run_commands(command, encoding='text')
    clean_command = messy_command[0]["output"]

    return clean_command


# based on commandType run as enable/config/show
def run_command(switch, commands):

    global commandType
    output = []

    if commandType == "enable":
        output.append("Running command: %s" % commands)
        output.append(enable_command(switch, commands))

    elif commandType == "config":
        output.append("Running command: %s" % commands)
        output.append(config_command(switch, commands))

    elif commandType == "show":
        output.append("Running command: %s" % commands)
        output.append(show_command(switch, commands))
        output.append("\n")

    else:
        output.append("\n\nWhat the hell just happened?\n\n")

    return output


# attempt connecting to a switch via pyeapi
def switch_connect(usern, pw, switch):

    try:
        node = pyeapi.connect(host=switch, username=usern, password=pw,
                              return_node=True)

    except pyeapi.eapilib.ConnectionError as err:
        print("WE ENCOUNTERED A CONNECTION ISSUE")
        print("Error command: %s" % err.command)
        print("Error message: %s" % err.message)

    return node


# grabs the running config from node and appends to a list to return
def grab_run(node, timing):

    config = []

    config.append("\nRunning-config from %s: " % timing)
    config.append(node.get_config(config='running-config'))
    config.append("-" * 30, "\n")

    return config


# load a file in and return a list of the lines
def load_file(filename):

    fileLines = []

    try:
        with open(filename) as readfile:
            for line in readfile:
                fileLines.append(line.strip())

    except IOError as msg:
        print("Error opening file " + filename)
        print(msg)

    return fileLines


# TODO Add a file per switch or a specified file name options
def write_output(contents):

    for item in contents:
        print(item)


# if -u was not used get the username via input
def get_username(username):

    if username == 'no_user_name':
        username = input("Enter your username: ")

    return username


# if -p was not used, use getpass to get the password
def get_password(password):

    if password == 'no_pass_word':
        password = getpass.getpass("Enter your password: ")

    return password


# -T, -t, or no switch; collect relevant switches into a list
def get_switch_list(filename, switch):

    # create the list of switches
    switchList = []

    # a list of switches filename was provided
    if filename != 'no_file_name':
        switchList = load_file(filename)

    # a single switch IP was provided
    elif switch != 'no_switch':
        switchList.append(switch)

    # no switches were provided ask for a single switch IP
    else:
        switchList.append(input("Enter the IP of the switch to connect to: "))

    return switchList


# -C, -c, or no command; collect relevant commands
def get_commands_list(commandfile, command):

    # create the list of commands we are going to run
    commandsList = []

    # if a list of commands filename was provided
    if commandfile != 'no_command_file':
        commandsList = load_file(commandfile)

    # if a single command was provided
    elif command != 'no_command':
        commandsList.append(command)

    # no commands were provided, ask for a single command
    else:
        commandsList.append(input("Enter the command to run: "))

    return commandsList


# TODO figure out a better way to determine show/config/enable
def set_command_type(command):

    global commandType

    # Take first command in the list, scope down to the first word in lowercase
    command = command[0]
    command = command.strip()
    command = command.split()
    command = command[0]
    command = command.lower()

    # compare the first two letters
    if command[:2] == 'en':
        commandType = "enable"

    elif command[:2] == 'sh':
        commandType = "show"

    elif command[:2] == 'co':
        commandType = "config"


# create the parser and return args
def parser():

    # Create the argument parser
    parser = argparse.ArgumentParser(description=(
        'Scott Cuthbert - Arista Command. ' +
        'This script is designed for Arista switches. ' +
        'You must enter the _entire_ command exactly!'))

    # -T to load file of switches
    parser.add_argument('-T', dest='multiswitch', nargs='?',
                        action='store', default='no_file_name',
                        help='defines the filename containing switches list')
    # -t to specify a target switch
    parser.add_argument('-t', dest='switch', nargs='?',
                        action='store', default='no_switch',
                        help='defines a single target switch')
    # -u to specify username
    parser.add_argument('-u', dest='username', nargs='?',
                        default='no_user_name', action='store',
                        help='defines the username to login with')
    # just for practice. leave commented out, use getpass instead
    parser.add_argument('-p', dest='password', nargs='?',
                        default='no_pass_word', action='store',
                        help='defines the password to login with')
    # -C for adding a file with a list of commands
    parser.add_argument('-C', dest='commandsfile', nargs='?',
                        action='store', default='no_command_file',
                        help='defines a filename containing commands to run')
    # -c for specifying a single command
    parser.add_argument('-c', dest='command', nargs='?', default='no_command',
                        action='store', help='define the command to send')
    # -s to specify a snapshot command
    parser.add_argument('-s', dest='snap', nargs='?',
                        action='store', default='no_snap',
                        help='defines a before/after snapshot command')
    # -S to specify a snapshot file
    parser.add_argument('-s', dest='multisnap', nargs='?',
                        action='store', default='no_snap_file',
                        help='defines the filename of snapshot commands list')
    # --change option to print running before and after commands issued
    parser.add_argument('--save', dest='grabrun', action='store_true',
                        help='Grab running-config before and after commands')

    # Create object args to reference
    args = parser.parse_args()

    return args


if __name__ == '__main__':
    main()
