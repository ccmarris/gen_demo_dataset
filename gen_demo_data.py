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

### Global Variables ###

# --- Classes ---

class METADATA:

    def __init__(self,cfg:str = 'metadata.yaml'):
        '''
        '''
        try:
            with open(cfg, 'r') as f:
                data = yaml.safe_load(f)
                self.metadata = data.get('metadata')
                self.config = data.get('config')
        except FileNotFoundError:
            logging.error(f'Metadata file {cfg} not found')
            raise

        self.def_headers()

        return
    

    def def_headers(self):
        '''
        '''
        self.container_header = ( 'header-networkcontainer,address*,netmask*,'
            'network_view,EA-Region,EAInherited-Region,EA-Country'
            ',EAInherited-Country,EA-Location,EAInherited-Location'
            ',EA-Department,EA-Billing,EA-SecurityZone,EA-VLAN' )

        self.net_header = ( 'header-network,address*,netmask*,routers,disabled,'
            'auto_create_reversezone,enable_discovery,'
            'EA-Region,EAInherited-Region,EA-Country,EAInherited-Country,'
            'EA-Location,EAInherited-Location,EA-Department,EA-Billing')

        self.dhcp_range_header = 'header-DhcpRange,start_address,end_address'
        self.nsg_header = ( 'header-nsgroup,group_name,grid_primaries,grid_secondaries,'
                            'is_grid_default' )
        self.zone_header = 'header-authzone,fqdn,zone_format,view,ns_group,soa_email'
        self.host_header = 'header-hostrecord,addresses,configure_for_dns,fqdn,EA-DeviceType'
        self.cname_header = 'header-CnameRecord,fqdn,view,canonical_name,comment,EA-DeviceType'
        self.headers = { 'containers': self.container_header,
                         'networks': self.net_header,
                         'dhcp_ranges': self.dhcp_range_header,
                         'nsg': self.nsg_header,
                         'auth_zones': self.zone_header,
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


    def dns_view(self):
        '''
        '''
        return self.config.get('dns_view')


    def name_server_group(self):
        '''
        '''
        return self.config.get('nsg')


    def auth_zones(self):
        '''
        '''
        return self.config.get('auth_zones')


    def cloud_providers(self):
        '''
        '''
        return self.config.get('cloud_providers').keys()


    def cloud_zones(self, cloud:str=''):
        '''
        '''
        zones:list = []
        cloud = cloud.casefold()

        if cloud:
            if cloud in self.cloud_providers():
                zones = self.config['cloud_providers'][cloud].get('zones')
            else:
                logging.error(f'Cloud vendor {cloud} not found')
        else:
            if self.cloud_providers():
                for c in self.cloud_providers():
                    zones.extend(self.config['cloud_providers'][c].get('zones'))
            else:
                logging.error('No cloud_providers found')
        
        return zones
            



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


    def gen_data(self, base:str=''):
        '''
        '''
        if base:
            self.gen_networks(base=base)
        else:
            self.gen_networks()
        self.gen_zones()
        self.gen_hosts()
        return
    

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
              f'{base_block.prefixlen},default,,,,,,,,No,,')

        # Create block per Region
        if len(regions) < len(sub_blocks):
            index = 0
            for region in regions:
                subnet = ipaddress.ip_network(sub_blocks[index])
                container_csv.append(f'networkcontainer,{subnet.network_address.exploded},'
                                     f'{subnet.prefixlen},default,'
                                     f'{region},OVERRIDE,,,,,,No,,')

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
                container_csv.append(f'networkcontainer,{sub.network_address.exploded},'
                                     f'{sub.prefixlen},default,,'
                                     f'INHERIT,{country},OVERRIDE,,,,No,,')
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
                container_csv.append(f'networkcontainer,{sub.network_address.exploded},'
                                     f'{sub.prefixlen},default,,'
                    f'INHERIT,,INHERIT,{location},OVERRIDE,,No,,')
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
        reverse:str = 'FALSE'

        # Gen prefix
        prefix = int(subnet.prefixlen + math.sqrt(len(departments))+2)
        # Don't create networks larger that /24
        if prefix < 24:
            prefix = 24
        subnets = list(subnet.subnets(new_prefix=prefix))
        if len(departments) < len(subnets):
            index = 0
            for dept in departments:
                sub = ipaddress.ip_network(subnets[index])
                gw = str(sub.network_address + 1)
                # Auto create reverse zone flag
                if sub.prefixlen == 24:
                    reverse = 'TRUE'
                else:
                    reverse = 'FALSE'
                networks.append(f'network,{sub.network_address.exploded},'
                                f'{sub.netmask.exploded},{gw},FALSE,{reverse},FALSE,,'
                                f'INHERIT,,INHERIT,,INHERIT,{dept},')
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

        return networks
        

    def dhcp_range(self, 
                   subnet:ipaddress.ip_network):
        '''
        Generate DHCP Ranges
    
        '''
        net_size = subnet.num_addresses
        if net_size > 254:
            range_size = 253
        elif net_size > 15:
            range_size = int(net_size / 2)
        else:
            range_size = int(net_size)
        broadcast = subnet.broadcast_address
        start_ip = str(broadcast - (range_size + 1))
        end_ip = str(broadcast - 1)
        logging.info(f"Creating Range start: {start_ip}, end: {end_ip}")

        range = f'DhcpRange,{start_ip},{end_ip}'
        
        if self.csv_sets.get('dhcp_ranges'):
            self.csv_sets['dhcp_ranges'].extend([ range ])
        else:
            self.csv_sets.update({'dhcp_ranges': [ range ] })

        return range


    def gen_zones(self):
        '''
        '''
        dns_view = self.dns_view()
        nsg = self.name_server_group()
        zones = self.auth_zones()
        lines:list = []

        # Gen NSG CSV
        self.csv_sets.update({ 'nsg': f'nsgroup,{nsg},,TRUE'})

        for z in zones:
            lines.append(f'authzone,{z},FORWARD,{dns_view},{nsg},demo@infoblox.com')
        
        if lines:
            self.csv_sets.update({'auth_zones': lines })

        return lines
    

    def gen_hosts(self, 
                  zone:str='infoblox.test', 
                  dns_view:str='Internal DNS'):
        '''
        '''
        return

### Functions ###

def parseargs():
    '''
    Parse Arguments Using argparse

    Parameters:
        None

    Returns:
        Returns parsed arguments
    '''
    description = 'NIOS Demo Data CSV Generator'
    parse = argparse.ArgumentParser(description=description)
    parse.add_argument('-c', '--config', type=str, default='metadata.yaml',
                        help="Override config file")
    parse.add_argument('-b', '--base', type=str, default='10.40.0.0/14',
                        help="Override config file")
    parse.add_argument('-f', '--file', action='store_true',
                        help='Output CSVs to file')
    parse.add_argument('-o', '--object', type=str, default='all',
                       help='Output specified object only')
    parse.add_argument('-d', '--debug', action='store_true', 
                        help="Enable debug messages")

    return parse.parse_args()


def setup_logging(debug):
    '''
     Set up logging

     Parameters:
        debug (bool): True or False.

     Returns:
        None.

    '''
    # Set debug level
    if debug:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s: %(message)s')
    else:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(levelname)s: %(message)s')

    return


def main():
    '''
    Code logic
    '''

    # Parse Arguments
    args = parseargs()
    setup_logging(args.debug)

    d = DEMODATA(include_countries=True, 
                 include_locations=True, 
                 include_networks=True, 
                 include_dhcp=True)
    d.gen_data(base=args.base)
    d.output_csv(object_type=args.object, to_file=args.file)

    return


### Main ###
if __name__ == '__main__':
    exitcode = main()
    exit(exitcode)
## End Main ###

    