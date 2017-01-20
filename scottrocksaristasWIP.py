#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Scott Cuthbert <cuthbes1@gene.com>

This script is designed for Arista switches.
Attempting to recreate the functionality of 'ciscocmd7k' without using expect

Allows input of a single command or multiple commands (via textfile) to be
run against a single switch or multiple switches (via textfile) and output
to either terminal, a single named file, or a file per switch

Currently only works with SHOW commands.


[changelog]
11-14-2016 - Initial version
11-17-2016 - Sectioned script into functions and updated parser with new args
11-18-2016 - Aligned document with PEP8 standards
11-18-2016 - Append former printmagic statements into a list to print later
11-18-2016 - Added output for single or multi file
11-18-2016 - Cleaned up the printmagic function to call other functions
11-21-2016 - Sped up the failed connection report: removed unneeded time.sleep
11-21-2016 - Removed errno 51 report from failed connection. Generic error now.
11-28-2016 - Moved parser into it's own function
11-28-2016 - Made debugging a global. Functions with debugging now use global
01-04-2017 - Added 'autoComplete=True' to pyeapi execute function
01-09-2017 - Added 'show hostname' as first command run each time
01-09-2017 - Working with JSON output
01-18-2017 - Updated global variables function to include 'autocomplete'
01-18-2017 - Renamed printmagic to scottrocks

TODO add better error checking, heh
TODO figure out the ssl script freakout thing
TODO determine logic to type shortened unambiguous commands ex "sh ip int b"
    This has been resolved by Matt - add [autoComplete=True] to command call
TODO add functionality beyond show commands
TODO utilize pyeapi as default (iron out the issues)
TODO fix multioutput issues
TODO add enable password checking

"""

# import time
import pyeapi
import argparse
import getpass
from jsonrpclib import Server
import ssl
import sys
from pprint import pprint


# TODO figure out why I need this or things go bonkers
ssl._create_default_https_context = ssl._create_unverified_context

# -d flag from parser. enables debugging throughout script
global debugging
debugging = False
# -a flag from parser. switches script from jsonrpc to pyeapi
global useapi
useapi = False
# -o flag from parser. filename for output append
# TODO do I need this as a global?
global fileout
# -A flag from parser. sets global autocomplete to true
# TODO create function to set this based on parse text command automatic
global autoCom
autoCom = False


def main():

    args = parser()

    # set the global variables
    set_globals(args.debug, args.api, args.autocomplete)

    # if show all commands was chosen, print them then exit
    if args.showall:
        output_all_commands()
        sys.exit()

    if debugging:
        sanity_check(args.switch, args.multiswitch,
                     args.username, args.password, args.command,
                     args.commandsfile, args.outfilename)

    # define variables, even if they werent parser provided
    username = get_username(args.username)
    password = get_password(args.password)
    switches = get_switch_list(args.multiswitch, args.switch)
    commands = get_commands_list(args.commandsfile, args.command)
    outType = get_output_type(args.multioutfile, args.outfilename)

    # the main squeeze
    scottrocks(switches, commands, username, password, outType)

    # print a universal truth. End of script.
    print ("\nScott Rocks\n")


# where the magic happens
def scottrocks(switchList, commandsList, user, password, outtype):

    for switch in switchList:

        # list that fills with info from ran commands, clears after each switch
        outputInfo = []
        outputInfo.append("Processing switch " + switch + "\n")

        try:
            node = switch_connect(user, password, switch)

            host_name = run_command(node, "show hostname")
            outputInfo.append(host_name)
            outputInfo.append("\n")

            for command in commandsList:

                outputInfo.append("Running command: " + command + "\n")
                cmdOutput = run_command(node, command)
                outputInfo.append(cmdOutput)
                outputInfo.append("\n")

        # TODO add more comprehensive error checking here
        except Exception as msg:
            outputInfo.append("Either could not open connection to " + switch +
                              " or could not run command\n")
            outputInfo.append("Exception msg = " + str(msg))

        write_output(switch, outtype, outputInfo)


# issues command to switch and returns output
def run_command(switch, command):

    if useapi:
        '''
        messy_command = switch.execute(command, encoding='text')
        clean_command = messy_command['result'][0]['output']
        '''
        messy_command = switch.execute(command, encoding='json')
        clean_command = messy_command['result'][0]

        pprint(clean_command)
    else:
        messy_command = switch.runCmds(1, [command], 'text')
        clean_command = messy_command[0]["output"]

    if debugging:
        print ('\nmessy_command = ' + str(messy_command))
        print ('\nclean_command = ' + str(clean_command))

    return clean_command


# connect to a switch, either with pyeapi or jsonrpc, return node object
def switch_connect(usern, passw, switch):

    if useapi:
        node = pyeapi.connect(host=switch, username=usern, password=passw)

    else:
        node = Server("https://" + usern + ":" + passw +
                      "@" + switch + "/command-api")

    return node


# TODO determine logic of unambiguous_command function
# UPDATE autoComplete=True could accomplish this
# UPDATE2 autoComplete=True might not function as exactly as expected
def unambiguous_command():
    print ("function not ready.")


# determine if multiple files, appended single file, or standard out
def get_output_type(multiout, singleout):

    # brings the global variable into function to possibly edit
    global fileout

    if singleout != 'no_outfile':
        fileout = singleout
        return 'a'

    elif multiout:
        return 'w'

    else:
        return 'p'


# load a file in and return a list of the lines
def load_file(filename):

    fileLines = []

    try:
        with open(filename) as readfile:
            for line in readfile:
                fileLines.append(line.strip())

    except IOError as msg:
        print ("Error opening file " + filename)
        print (msg)

    return fileLines


# TODO this whole function looks messy. Clean it up
# based on write_type: either print, make one file, or make file per switch
def write_output(filename, write_type, contents):

    try:
        # print to standard out
        if write_type == 'p':
            for item in contents:
                print (item)

        # print append to a single file
        # TODO fix reference / check working reference
        elif write_type == 'a':
            with open((fileout + ".txt"), write_type) as data:
                for item in contents:
                    data.write(item)

        # print to a different file for each switch (uses switchname)
        # TODO make each switchname a somehow relevant filename
        elif write_type == 'w':
            with open(filename, write_type) as data:
                for item in contents:
                    data.write(item)

    except IOError as msg:
        print ("Couldn't output.")
        print (msg)


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

    # prints the values loaded in from the file - part of debug sanity check
    if debugging:
        print("These are the values found within switchList: ", switchList)

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

    # prints the values loaded in from the file - part of debug sanity check
    if debugging:
        print("These are the values found within commandsList: ", commandsList)

    return commandsList


# Sanity check parser flags
def sanity_check(switch, mswitchf, user, passw, command,
                 commandfile, outfile):

    print("\n--- Sanity checking all inputs ---")
    print("the global debugging value was: " + str(debugging) + ' ...duh')
    print("the global useapi value was: " + str(useapi))
    print("the specified target switch was: ", switch)
    print("the specified mutltiswitch file was: ", mswitchf)
    print("the username specified was: ", user)
    print("the password specified was: ", passw)
    print("the command specified was: ", command)
    print("the commands filename specified was: ", commandfile)
    print("the outfile name specified was: ", outfile)
    print("--- Sanity check over ---\n\n")


# sets the global variables
def set_globals(debug, api, complete):

    if debug:
        global debugging
        debugging = True

    if api:
        global useapi
        useapi = True

    if complete:
        global autoCom
        autoCom = True


# create the parser and return args
def parser():

    # Create the argument parser
    parser = argparse.ArgumentParser(description=(
        'Scott Cuthbert - Arista Show Command. ' +
        'This script is designed for Arista switches. ' +
        'Currently only works with show commands. ' +
        'You must enter the entire command exactly!'))  # if not using pyeapi

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
    # -d to enable script debugging
    parser.add_argument('-d', dest='debug', action='store_true',
                        help='turn on script sanity check debugging')
    # -O to create a file for each switch's output
    parser.add_argument('-O', dest='multioutfile', action='store_true',
                        help='write output to a file for each switch')
    # -o to create a single file with all output
    parser.add_argument('-o', dest='outfilename', nargs='?',
                        default='no_outfile', action='store',
                        help='write output to a single file')
    # -Z option to dump all available commands to standard out
    parser.add_argument('-Z', dest='showall', action='store_true',
                        help='print all available commands and exit.')
    # -a option to enable use of pyeapi instead of jsonrpc
    parser.add_argument('-a', dest='api', action='store_true',
                        help='use pyeapi to connect to node')
    # -A option to enable use of autoComplete
    parser.add_argument('-A', dest='autocomplete', action='store_true',
                        help='attempt to autocomplete commands - unfinished')

    # Create object args to reference
    args = parser.parse_args()

    return args


# print all the commands available to the command-api.
# requires 'listofcommands.txt' be in directory
def output_all_commands():

    print("\nAlright, you asked for it. Printing all supposedly " +
          "available commands.\nAlso ignoring all other input at this time.\n")

    availableComms = load_file("listofcommands.txt")

    for item in availableComms:
        print (item)


main()
