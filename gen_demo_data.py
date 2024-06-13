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
            ',EA-Location,EAInherited-Location,EA-Datacentre'
            ',EA-Department,EA-Billing,EA-SecurityZone,EA-VLAN,EA-Tenant ID' )

        self.host_header = 'header-hostrecord,addresses,configure_for_dns,fqdn,EA-DeviceType'
        self.zone_header = 'header-authzone,fqdn,zone_format,ns_group,comment'
        self.cname_header = 'header-CnameRecord,fqdn,view,canonical_name,comment,EA-DeviceType'

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
                 postfix:str = 'demo'):
        '''
        '''
        super().__init__(metadata)
        self.postfix = postfix
        self.csv_sets:dict = {}

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
    
    
    def output_csv(self, to_file:bool = False):
        '''
        '''
        # Output each section
        for object in self.csv_sets.keys():
            # Set output mechanism
            if to_file:
                output = self.open_csv(filename=f'{object}_{self.postfix}.csv')
            else:
                output = sys.stdout

            # Ouput lines
            for line in self.csv_sets[object]:
                print(line, file=output)
        
        return

    def gen_containers(self, 
                       base:str = '10.40.0.0/14', 
                       include_countries:bool = False,
                       include_locations:bool = False):
        '''
        '''
        container_csv:list = []
        dhcp_ranges:list = []
        regions = self.regions()
        base_block = ipaddress.ip_network(base)
        next_prefix = int(base_block.prefixlen + math.sqrt(len(regions)) + 1)
        sub_blocks = list(base_block.subnets(new_prefix=next_prefix))


        # Ouput container header
        container_csv.append(self.container_header)

        # Create Top Level container
        container_csv.append(f'networkcontainer,{base_block.network_address.exploded},'
              f'{base_block.prefixlen},,,,default,,,,,,,,,,No,,')

        # Create block per Region
        if len(regions) < len(sub_blocks):
            index = 0
            for region in regions:
                subnet = ipaddress.ip_network(sub_blocks[index])
                container_csv.append(f'networkcontainer,{subnet.exploded},,,,default,,{region},'
                    f'OVERRIDE,,,,,,,No,,')

                # Add countries if included
                if include_countries:
                    container_csv.extend(self.country_containers(subnet=subnet, 
                                                                region=region,
                                                                include_locations=include_locations))
                elif include_locations:
                    logging.warning(f'To create city containers for {region} include_country=True is required')

                index += 1
        else:
            logging.error(f'Base subnet {base} cannot be subnetted in'
                          f'to {len(regions)} regions.')

        if container_csv:
            self.csv_sets.update({ 'containers': container_csv})
        if dhcp_ranges:
            self.csv_sets.update({ 'dhcp_ranges': dhcp_ranges})


        return self.csv_sets


    def country_containers(self, 
                           subnet:ipaddress.ip_network, 
                           region:str,
                           include_locations:bool = False):
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
                container_csv.append(f'networkcontainer,{sub.exploded},,,,default,,,'
                    f'INHERIT,{country},OVERRIDE,,,,,No,,')
                # Add locations if included
                if include_locations:
                    container_csv.extend(self.location_containers(subnet=sub, 
                                                                  country=country)
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
                container_csv.append(f'networkcontainer,{sub.exploded},,,,default,,,'
                    f'INHERIT,,INHERIT,{location},OVERRIDE,,,No,,')
                index += 1

        else:
            logging.error(f'subnet {subnet} cannot be subnetted in'
                        f'to {len(locations)} countries.')

        return container_csv




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
    #regions = ['EMEA', 'Americas', 'APAC', 'Turkey']
    regions = ['EMEA', 'Americas', 'APAC']
    countries = {
        'EMEA' : ['Germany', 'Greece', 'Luxembourg', 'Saudi Arabia',
        'South Africa', 'Malta', 'Monaco', 'Switzerland', 'Turkey',
        'UAE', 'United Kingdom'],
        'Americas' : ['Argentina', 'Canada', 'Mexico', 'United States'],
        'APAC' : ['Australia', 'China', 'Hong Kong', 'India', 'Japan', 'Malaysia', 'Singapore'],
        'Turkey':['Turkey']
        }
    locations = {
        'Germany':['Dusseldorf','Leverkusen'],
        'Greece':['Athens'],
        'Luxembourg':['Luxembourg'],
        'Saudi Arabia':['Jeddah','Riyadh'],
        'South Africa':['Johannesburg'],
        'Malta':['Figura','Qormi'],
        'Monaco':['Monaco'],
        'Switzerland':['Geneva','Plan Les Quates'],
        'Turkey':['Istanbul','Izmir'],
        'UAE':['Dubai'],
        'United Kingdom':['London','Slough','Barnsley','Wakefield'],
        'Argentina':['Buenos Aires'],
        'Canada':['Toronto','Vancouver'],
        'Mexico':['Mexico City'],
        'United States':['Bermuda','New York','Chicago'],
        'Australia':['Melbourne','Sydney'],
        'China':['Foshan','Shanghai'],
        'Hong Kong':['Hong Kong'],
        'India':['Bangalore','Hyderabad','Kolkatta','Mumbai'],
        'Japan':['Tokyo','Osaka'],
        'Malaysia':['Cyberjaya','Kuala Lumpur'],
        'Singapore':['Singapore']
        }

    datacentres = {
        'Buenos Aires':['Buenos Aires DC1','Buenos Aires DC2'],
        'Melbourne':['Melbourne DC1'],
        'Sydney':['Sydney DC2'],
        'Toronto':['Toronto DC2'],
        'Vancouver':['Vancouver DC1'],
        'Foshan':['Foshan DC1'],
        'Shanghai':['Shanghai DC2'],
        'Dusseldorf':['Dusseldorf DC1'],
        'Leverkusen':['Leverkusen DC2'],
        'Athens':['Athens DC1','Athens DC2'],
        'Hong Kong':['Hong Kong DC1','Hong Kong DC2'],
        'Bangalore':['Bangalore DC1'],
        'Hyderabad':['Hyderabad DC2'],
        'Kolkatta':['Kolkatta DC3'],
        'Mumbai':['Mumbai DC4'],
        'Osaka':['Osaka DC2'],
        'Tokyo':['Tokyo DC1'],
        'Luxembourg':['Luxembourg DC1 (PB)'],
        'Cyberjaya':['Cyberjaya DC2'],
        'Kuala Lumpur':['Kuala Lumpur DC1'],
        'Figura':['Figura DC1'],
        'Qormi':['Qormi DC1'],
        'Mexico City':['Chapulepec DC1'],
        'Mexico City':['Toluca DC2'],
        'Monaco':['Monaco DC1','Monaco DC2'],
        'Jeddah':['Jeddah DC1'],
        'Riyadh':['Riyadh DC2'],
        'Singapore':['Singapore DC1','Singapore DC2'],
        'Johannesburg':['Johannesburg DC1','Johannesburg DC2'],
        'Geneva':['Geneva DC1'],
        'Plan Les Quates':['Plan Les Quates DC2'],
        'Istanbul':['Istanbul DC1'],
        'Izmir':['Izmir DC2'],
        'Dubai':['Dubai DC1','Dubai DC2'],
        'London':['London DC1 (IB)'],
        'Slough':['Slough DC2 (IB)'],
        'Barnsley':['South Yorkshire DC1'],
        'Wakefield':['Wakefield DC2'],
        'Bermuda':['Bermuda DC1','Bermuda DC2'],
        'New York':['New Jersey DC1 (IB)'],
        'New York':['New York DC2 (IB)'],
        'Chicago':['Northlake DC2'],
        'Chicago':['Vernon Hills DC1']
        }
    departments = ['Human Resources','Private Banking','Trading','Infrastructure','Office Services','Networks','Branches']
    billing = ['Yes','No']
    securityzones = ['Internet','Zone1','Internet DMZ','Internal','Internal DMZ','Red','Blue']


    # Select Random EAs
    eas['Region'] = random.choice(regions)
    eas['Country'] = random.choice(countries[eas['Region']])
    eas['Location'] = random.choice(locations[eas['Country']])
    eas['Datacentre'] = random.choice(datacentres[eas['Location']])
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
                print('hostrecord,{0}.{1}.{2}.{3},TRUE,host-{0}-{1}-{2}-{3}.{4},{5}'.format(baseoct,o2,o3,o4,zone,dev))
    
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