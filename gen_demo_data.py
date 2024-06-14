#!/usr/local/bin/python3
#vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
"""
-----------------------------------------------------------------------

 Generate Networks for import in to Infoblox

 Requirements:
   Python 3

 Usage: <scriptname> [options]
        -d        dump mode (dump message as-is)
        -t        test mode (no actions taken)
        -h        help
        -v        verbose

 Author: Chris Marrison
 Email: chris@infoblox.com

 ChangeLog:
   <date>	<version>	<comment>

 Todo:

 Copyright 2018 Chris Marrison / Infoblox Inc

 Redistribution and use in source and binary forms,
 with or without modification, are permitted provided
 that the following conditions are met:

 1. Redistributions of source code must retain the above copyright
 notice, this list of conditions and the following disclaimer.

 2. Redistributions in binary form must reproduce the above copyright
 notice, this list of conditions and the following disclaimer in the
 documentation and/or other materials provided with the distribution.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
 ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 POSSIBILITY OF SUCH DAMAGE.
----------------------------------------------------------------------
"""

__version__ = '0.0.5'
__author__ = 'Chris Marrison'

import logging
import os
import sys
import shutil
import math
import yaml
import argparse
import ipaddress
import random
import collections

### Global Variables ###

nets = 10
baseoct = 12
oct2 = 0
oct3 = 0
oct4 = 0
subnet = 24
mask = '255.255.255.0'


class METADATA:

    def __init__(self,cfg:str = 'metadata.yaml'):
        '''
        '''
        try:
            with open(cfg, 'r') as f:
                data = yaml.safe_load(f)
                self.metadata = data.get('metadata')
        except FileNotFoundError:
            logging.error(f'Metadata file {cfg} not found')
            raise

        self.def_headers()

        return
    

    def def_headers(self):
        '''
        '''
        self.container_header = ( 'header-networkcontainer,address*,netmask*,discovery_exclusion_range'
            ',discovery_member,enable_discovery,network_view,zone_associations'
            ',EA-Region,EAInherited-Region,EA-Country'
            ',EAInherited-Country,EA-Location,EAInherited-Location'
            ',EA-Department,EA-Billing,EA-SecurityZone,EA-VLAN' )

        self.net_header = ( 'header-network,address*,netmask*,disabled,enable_discovery'
            ',EA-Region,EAInherited-Region,EA-Country,EAInherited-Country'
            ',EA-Location,EAInherited-Location,EA-Department,EA-Billing')

        self.zone_header = 'header-authzone,fqdn,zone_format,ns_group,comment'
        self.host_header = 'header-hostrecord,addresses,configure_for_dns,fqdn,EA-DeviceType'
        self.cname_header = 'header-CnameRecord,fqdn,view,canonical_name,comment,EA-DeviceType'
        self.headers = { 'containers': self.container_header,
                         'networks': self.net_header,
                         'zones': self.zone_header,
                         'hosts': self.host_header,
                         'cnames': self.cname_header }

        return

    
    def names(self):
        '''
        '''
        return self.metadata.get['names']


    def regions(self):
        '''
        '''
        return list(self.metadata['location_data'].keys())
    

    def countries(self, region:str = '') -> list:
        '''
        '''
        countries:list = []

        if region:
            countries = list(self.metadata['location_data'][region].keys())
        else:
            for region in self.metadata['location_data'].keys():
                countries.extend(list(self.metadata['location_data'][region].keys()))
        
        return countries
    

    def get_region(self, country:str):
        '''
        '''
        region:str = ''
        for r in self.regions():
            if country in self.metadata['location_data'][r].keys():
                region = r
                break
        
        return region


    def locations(self, region:str = '', country:str = ''):
        '''
        '''
        locations:list = []

        if region and country:
            locations = self.metadata['location_data'][region][country]
        elif region:
            for ctry in self.countries(region=region):
                locations.extend(self.metadata['location_data'][region][ctry])
        elif country:
            region = self.get_region(country=country)
            locations = self.metadata['location_data'][region][country]

        return locations


    def departments(self):
        '''
        '''
        return self.metadata.get('departments')


    def device_types(self):
        '''
        '''
        return self.metadata.get('device_types')


    def org_compartments(self):
        '''
        '''
        return self.metadata.get('org_compartments')



class DEMODATA(METADATA):

    def __init__(self, 
                 metadata:str = 'metadata.yaml',
                 postfix:str = 'demo',
                 include_countries:bool = False,
                 include_locations:bool = False,
                 include_networks:bool = False,
                 include_dhcp:bool = False):
        '''
        '''
        super().__init__(metadata)
        self.postfix = postfix
        self.csv_sets:dict = {}
        self.include_countries:bool = include_countries
        self.include_locations:bool = include_locations
        self.include_networks:bool = include_networks
        self.include_dhcp:bool = include_dhcp

        return
    

    def open_csv(self, filename:str = 'data.csv') -> object:
        '''
        Attempt to open output file

        Parameters:
            filename (str): Name of file to open.

        Returns:
            file handler object.

        '''
        if os.path.isfile(filename):
            backup = filename+".bak"
            try:
                shutil.move(filename, backup)
                logging.info("Outfile exists moved to {backup}")
                try:
                    handler = open(filename, mode='w')
                    logging.info(f"Successfully opened output file {filename}.")
                except IOError as err:
                    logging.error(f"{err}")
                    handler = False
            except IOError:
                logging.warning(f"Could not backup existing file {filename}.")
                handler = False
        else:
            try:
                handler = open(filename, mode='w')
                logging.info(f"Successfully opened output file {filename}.")
            except IOError as err:
                logging.error(f"{err}")
                handler = False

        return handler
    
    
    def output_csv(self,
                   object_type:str = 'all',
                   to_file:bool = False):
        '''
        '''
        if object_type == 'all':
            # Output each section
            for object in self.csv_sets.keys():
                # Set output mechanism
                if to_file:
                    output = self.open_csv(filename=f'{object}_{self.postfix}.csv')
                else:
                    output = sys.stdout

                # Output header for object
                header = self.headers.get(object)
                print(header, file=output)
                # Ouput lines
                for line in self.csv_sets[object]:
                    print(line, file=output)
        elif object_type in self.csv_sets.keys():
            # Set output mechanism
            if to_file:
                output = self.open_csv(filename=f'{object_type}_{self.postfix}.csv')
            else:
                output = sys.stdout

            # Output header for object
            header = self.headers.get(object_type)
            print(header, file=output)
            # Ouput lines
            for line in self.csv_sets[object_type]:
                print(line, file=output)
        
        else:
            logging.error(f'No data generated for object type: {object_type}')
        
        return


    def get_header_for_obj(self, object_type:str=''):
        '''
        '''
        # Match object type and return header
        return self.headers.get(object_type)


    def gen_networks(self, 
                       base:str = '10.40.0.0/14'):
        '''
        '''
        container_csv:list = []
        regions = self.regions()
        base_block = ipaddress.ip_network(base)
        next_prefix = int(base_block.prefixlen + math.sqrt(len(regions)) + 1)
        sub_blocks = list(base_block.subnets(new_prefix=next_prefix))

        # Create Top Level container
        container_csv.append(f'networkcontainer,{base_block.network_address.exploded},'
              f'{base_block.prefixlen},,,,default,,,,,,,,,,No,,')

        # Create block per Region
        if len(regions) < len(sub_blocks):
            index = 0
            for region in regions:
                subnet = ipaddress.ip_network(sub_blocks[index])
                container_csv.append(f'networkcontainer,{subnet.network_address.exploded},'
                                     f'{subnet.prefixlen},,,default,,'
                                     f'{region},' f'OVERRIDE,,,,,,,No,,')

                # Add countries if included
                if self.include_countries:
                    container_csv.extend(self.country_containers(subnet=subnet, 
                                                                region=region))
                elif self.include_locations:
                    logging.warning(f'To create city containers for {region} include_country=True is required')

                index += 1
        else:
            logging.error(f'Base subnet {base} cannot be subnetted in'
                          f'to {len(regions)} regions.')

        if container_csv:
            self.csv_sets.update({ 'containers': container_csv})


        return self.csv_sets


    def country_containers(self, 
                           subnet:ipaddress.ip_network, 
                           region:str):
        '''
        '''
        container_csv:list = []

        countries = self.countries(region=region)
        # Create block per country 
        country_prefix = int(subnet.prefixlen + math.sqrt(len(countries))+2)
        country_blocks = list(subnet.subnets(new_prefix=country_prefix))
        if len(countries) < len(country_blocks):
            index = 0
            for country in countries:
                sub = ipaddress.ip_network(country_blocks[index])
                container_csv.append(f'networkcontainer,{sub.network_address.exploded}'
                                     f'{sub.prefixlen},,,,default,,,'
                                     f'INHERIT,{country},OVERRIDE,,,,,No,,')
                # Add locations if included
                if self.include_locations:
                    container_csv.extend(self.location_containers(subnet=sub, 
                                                                  country=country))
                index += 1

        else:
            logging.error(f'subnet {subnet} cannot be subnetted in'
                        f'to {len(countries)} countries.')

        return container_csv


    def location_containers(self, 
                            subnet:ipaddress.ip_network, 
                            country:str):
        '''
        '''
        container_csv:list = []

        locations = self.locations(country=country)
        # Create block per country 
        prefix = int(subnet.prefixlen + math.sqrt(len(locations))+2)
        blocks = list(subnet.subnets(new_prefix=prefix))
        if len(locations) < len(blocks):
            index = 0
            for location in locations:
                sub = ipaddress.ip_network(blocks[index])
                container_csv.append(f'networkcontainer,{sub.network_address.exploded}'
                                     f'{sub.prefixlen},,,,default,,,'
                    f'INHERIT,,INHERIT,{location},OVERRIDE,,,No,,')
                # Add networks if included
                if self.include_networks:
                    self.create_networks(subnet=sub, location=country)
                index += 1

        else:
            logging.error(f'subnet {subnet} cannot be subnetted in'
                        f'to {len(locations)} countries.')

        return container_csv


    def create_networks(self, 
                        subnet:ipaddress.ip_network,
                        location:str):
        '''
        '''
        networks:list = []
        dhcp_csv:list = []
        departments = self.departments()

        # Gen prefix
        prefix = int(subnet.prefixlen + math.sqrt(len(departments))+2)
        subnets = list(subnet.subnets(new_prefix=prefix))
        if len(departments) < len(subnets):
            index = 0
            for dept in departments:
                sub = ipaddress.ip_network(subnets[index])
                networks.append(f'network,{sub.network_address.exploded},'
                                f'{sub.netmask.exploded}',FALSE,FALSE,,'
                                f'INHERIT,,INHERIT,,INHERIT,{dept},OVERIDE')
                # Add networks if included
                if self.include_dhcp:
                    dhcp_csv.append(self.dhcp_range(subnet=sub))
                index += 1

        else:
            logging.error(f'subnet {subnet} cannot be subnetted in'
                        f'to {len(self.departments)} countries.')
        
        # Update csv_sets
        if networks:
            if self.csv_sets.get('networks'):
                self.csv_sets['networks'].extend(networks)
            else:
                self.csv_sets.update({'networks': networks })

        if dhcp_csv:
            if self.csv_sets.get('dhcp_ranges'):
                self.csv_sets['dhcp_ranges'].extend(dhcp_csv)
            else:
                self.csv_sets.update({'dhcp_ranges': dhcp_csv })

        return networks
        

    def dhcp_range(self, 
                    subnet:ipaddress.ip_network):
        '''
        '''
        net_size = subnet.num_addresses
        range_size = int(net_size / 2)
        broadcast = subnet.broadcast_address
        start_ip = str(broadcast - (range_size + 1))
        end_ip = str(broadcast - 1)
        gw = str(subnet.network_address + 1)
        logging.info("Creating Range start: {}, end: {}".format(start_ip, end_ip))

        range = f''
        
        if self.csv_sets.get('dhcp_ranges'):
            self.csv_sets['dhcp_ranges'].extend(range)
        else:
            self.csv_sets.update({'dhcp_ranges': range })

        return networks

### Functions ###

def parseargs():
    """
     Parse Arguments Using argparse

        Returns arguments
    """
    parse = argparse.ArgumentParser(description='Infoblox CSV Import Generator')

    #parse.add_argument('-o', '--output', type=str, help="CSV Output to <filename>")
    #parse.add_argument('-s', '--silent', action='store_true', help="Silent mode")
    parse.add_argument('-i', '--iterations', type=int, default=10, choices=range(1,256),
            metavar="[1-255]", help="Number of containers/networks to create")
    parse.add_argument('-b', '--base', type=int, default=10, choices=range(1,255),
            metavar="[1-254]",help="IPv4 Base Octet")
    parse.add_argument('-c', '--containers', action='store_true', help="Create network containers only")
    parse.add_argument('-z', '--zone', type=str, default="local", help="Base zone")

    return parse.parse_args()

"""
def gen_eas():
    eas = collections.defaultdict()
    extattrs = ['Region', 'Country', 'Location', 'Datacentre', 'Department', 'Billing', 'SecurityZone', 'VLAN']

    # Select Random EAs
    eas['Region'] = random.choice(regions)
    eas['Country'] = random.choice(countries[eas['Region']])
    eas['Location'] = random.choice(locations[eas['Country']])
    eas['Department'] = random.choice(departments)
    eas['Billing'] = random.choice(billing)
    eas['SecurityZone'] = random.choice(securityzones)
    eas['VLAN'] = random.randint(100,4095)

    return eas


### Main ###

# Parse Arguments
args = parseargs()
baseoct = args.base
nets = args.iterations
containers_only = args.containers

# Output container header
print(cheader)
# Output network header
print(nheader)

def gen_containers():
    '''
    '''
    # Gen initial /8
    subnet = 8
    print('networkcontainer,{}.{}.{}.{},{},,,,default,,,,,,'
            ',,,,No,,'.format(baseoct, oct2, oct3, oct4, subnet))

    # Gen /16 containers
    for o2 in range(nets):
        subnet = 16
        eas = gen_eas()
        oct2 = o2
        print('networkcontainer,{}.{}.{}.{},{},,,,default,,{},OVERRIDE,{},OVERRIDE,'
            '{},OVERRIDE,{},,No,,'.format(baseoct, oct2, oct3, oct4, subnet,
            eas['Region'],eas['Country'],eas['Location'],eas['Datacentre']))

        if not containers_only:
            # Gen /24 subnets
            for o3 in range(nets):
                oct3 = o3
                print('network,{}.{}.{}.{},{},FALSE,FALSE,,INHERIT,'
                    ',INHERIT,,INHERIT,,{},{},{},{},1011'.format(baseoct, oct2, oct3, oct4, mask,
                    eas['Department'],eas['Billing'],eas['SecurityZone'],eas['VLAN']))

    return
                                


def gen_hosts():
    '''
    '''
    # Output host header
    print(header)

    # Iterate through second octet
    for o2 in range(255):
        #eas = gen_eas()
        oct2 = o2

        # Gen /24 subnets
        for o3 in range(255):
            oct3 = o3

            # Gen host data
            for o4 in range(iterations):
                dev = random.choice(devices)
    
    return

def gen_zones():
    '''
    '''
    # Output host header
    print(zheader)

    # Iterate
    for n in range(iterations):
        prefix = random.choice(prefixes)
        print('authzone,{}-{}.{},FORWARD,internal,chris@infoblox.com'.format(prefix,n,zone))
    
    return


def gen_cnames():
    '''
    '''
    # Output host header
    print(header)

    # Iterate through second octet
    for o2 in range(iterations):
        #eas = gen_eas()
        oct2 = o2

        # Gen /24 subnets
        for o3 in range(255):
            oct3 = o3

            # Gen host data
            for o4 in range(iterations):
                dev = random.choice(devices)
                print('CnameRecord,host-{0}-{1}-{2}-{3}.{4},default,host-{3}.test.poc,"Import Test",{5}'.format(baseoct,o2,o3,o4,zone,dev))
    
    return
"""