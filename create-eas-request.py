#!/usr/local/bin/python
############################################################################
# ABSOLUTELY NO WARRANTY WITH THIS PACKAGE. USE IT AT YOUR OWN RISK.
#
# Create EAs using WAPI
#
# Requirements:
#   requests, getpass
#
# Usage: <scriptname> 
#
# Author: Chris Marrison
#
# ChangeLog:
#   20170901    0.5     Added basic API error handling
#   20170901    0.3     Added file check for ea_list.txt
#   20170831    0.2     Request username:password
#   20170829	0.1	Basic working principle
#
# Todo:
#   Error Handling
#
# Copyright (c) 2017 All Rights Reserved.
############################################################################

import requests
import getpass
import argparse
from pathlib import Path

file = Path("ea_list.txt")
ea_list = []
wapi_url = "https://192.168.0.242/wapi/v2.11"


def parseargs():
    '''
    Parse Arguments Using argparse

    Parameters:
        None

    Returns:
        Returns parsed arguments
    '''
    parse = argparse.ArgumentParser(description='Create EA in NIOS')
    parse.add_argument('-f', '--file', type=str, default='ea_list.txt',
                        help="Overide EA List file")
    parse.add_argument('-d', '--debug', action='store_true', 
                        help="Enable debug messages")

    return parse.parse_args()


### Main ###

args = parseargs()
if args.file:
    file = Path(args.file)
else:
    file = Path("ea_list.txt")

# Disable SSL warnings in requests #
requests.packages.urllib3.disable_warnings()

# Read list of EA from file - one per line #
if file.is_file():
    for line in open(file):
        ea_list.append(line.rstrip())
else:
    print("File: " + str(file) + " not found.")
    exit()


# Get username and password for auth #
user = input('Username: ')
passwd = getpass.getpass('Password: ')

# Create each EA in ea_list #
for ea in ea_list:
    payload = '{"name": "'+ea+'","type": "STRING", "flags":"I"}'

    headers = {
        'content-type': "application/json"
        }

    print("Adding EA: " + ea, end=" : ")

    # Call POST /extensibleattributedef
    response = requests.request("POST", wapi_url+"/extensibleattributedef", data=payload, 
		    headers=headers, auth=(user,passwd), verify=False)

    if response.status_code == 201:
        print("Success.")
    else:
        print("Failed.") 
        print(response.text)



