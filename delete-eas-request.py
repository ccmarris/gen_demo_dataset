#!/usr/local/bin/python
############################################################################
# ABSOLUTELY NO WARRANTY WITH THIS PACKAGE. USE IT AT YOUR OWN RISK.
#
# Delete EAs using WAPI
#
# Requirements:
#   requests, getpass
#   Reads EAs from file with one EA per line (ea_list.txt)
#
# Usage: <scriptname> 
#
# Author: Chris Marrison
#
# ChangeLog:
#   20170904	0.5	Added basic API error handling
#   20170901	0.3	Version number consistency
#   20170901	0.2	Added file check for ea_list.txt
#   20170831	0.1	Built from create-eas-request.py
#
# Todo:
#   Error Handling
#
# Copyright (c) 2017 All Rights Reserved.
############################################################################

import requests
import getpass
from pathlib import Path

file = Path("ea_list.txt")
ea_list = []
wapi_url = "https://192.168.0.242/wapi/v2.11.1"

### Main ###

# Disable SSL warnings in requests #
requests.packages.urllib3.disable_warnings()

# Read list of EA from file - one per line #
if file.is_file():
    for line in open(file):
        ea_list.append(line.rstrip())
else:
    print("File: " + str(file) + " not found.")
    exit()

for line in open(file):
	    ea_list.append(line.rstrip())

# Get username and password for auth #
user = input('Username: ')
passwd = getpass.getpass('Password: ')

# Create each EA in ea_list #
for ea in ea_list:
    payload = ( '['
                    '{'
                        '"method": "STATE:ASSIGN",'
                        '"data": {'
                                '"ea_name": "' + ea + '"'
                                '}'
                    '},'
                    '{'
                        '"method": "GET",'
                        '"object": "extensibleattributedef",'
                        '"data": {'
                                '"name": "##STATE:ea_name:##"'
                                '},'
                        '"assign_state": {'
                                '"ea_ref": "_ref"'
                                '},'
                        '"enable_substitution": true,'
                        '"discard": true'
                     '},'
                     '{'
                        '"method": "DELETE",'
                        '"object": "##STATE:ea_ref:##",'
                        '"enable_substitution": true,'
                        '"discard": true'
                     '},'
                     '{'
                        '"method": "STATE:DISPLAY"'
                     '}'
                ']')

    headers = {
        'content-type': "application/json"
        }

    print("Deleting EA: " + ea, end=" : ")

    # Call POST /request obj
    response = requests.request("POST", wapi_url+"/request", data=payload, 
		    headers=headers, auth=(user,passwd), verify=False)

    if response.status_code == 201:
        print("Success.")
    else:
        print("Failed.")
        print(response.text)


