#
# Copyright (C) 2011 Radicore AB.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA
#
# Author: Lars Sjostrom <lars@radicore.se>

import web
import xmlrpclib
import random
import os
import time

server = xmlrpclib.Server("http://localhost/cobbler_api")

def get_token(user, password):
    try:
        token = server.login(user, password)
        return token
    except xmlrpclib.Fault, f:
        return None

def test_token(token):
    try: 
        if server.token_check(token):
            return True
    except:
        pass

    return False

def get_profiles():
    try:
        return [ p['name'] for p in server.get_profiles() ]
    except IndexError:
        return None

def get_org_id(profile):
    try:
        return server.get_profile(profile)['ks_meta']['org']
    except:
        return None

def get_systems():
    try:
        d = []
        for s in server.get_systems():
            d.append({"name" : s['name'], "uid" : s['uid']})
        return d
    except:
        return None

def get_formdata_by_uid(uid):
    
    s = server.find_system({'uid': uid})[0]
    if not s:
        return None

    d = server.get_system(s)
    
    iface = d['interfaces'].keys()
                
    formdata = {    
        'name': d['name'],
        'hostname': d['hostname'],
        'mac_address': d['interfaces'][iface[0]]['mac_address'],
        'ip_address': d['interfaces'][iface[0]]['ip_address'],
        'subnet': d['interfaces'][iface[0]]['subnet'],
        'gateway': d['gateway'],
        'name_servers': " ".join(d['name_servers']),
        'name_servers_search': " ".join(d['name_servers_search']),
        'profile': d['profile'],
        'redhat_management_key': d['redhat_management_key']
    }

    if "bond0" in d['interfaces'] and len(d['interfaces']) > 2:
        formdata['bonding'] = True
        formdata['bonding_opts'] = d['interfaces']['bond0']['bonding_opts']
        formdata['eth_name1'] = iface[1]
        formdata['mac_addr1'] = d['interfaces'][iface[1]]['mac_address']
        formdata['eth_name2'] = iface[2]
        formdata['mac_addr2'] = d['interfaces'][iface[2]]['mac_address']
    
    return formdata

def remove_system(uid, token):

    name = server.find_system({'uid': uid})[0]
    if not name:
        return None

    try:
        return server.remove_system(name, token)
    
    except xmlrpclib.Fault, f:
        if f.faultCode == 1:
            raise web.seeother('/logout')

def crud_system(opts, token):

    # find out if we are using Spacewalk/RHN Satellite
    org = get_org_id(opts['profile'].value)
    if org:
        name = opts['hostname'].value + ":" + str(org)
    else:
        name = opts['hostname'].value

    # See if you should update or create new
    if not opts['name'].value:
        try:
            if server.find_system({'name': name}):
                return "System name already exists"
            system_id = server.new_system(token)
            server.modify_system(system_id,'name', name, token)

        except xmlrpclib.Fault, f:
            return f.faultString
    else:
        try:
            system_id = server.get_system_handle(opts['name'].value, token)
            server.rename_system(system_id, name, token)
            system_id = server.get_system_handle(name, token)

        except xmlrpclib.Fault, f:
            return f.faultString

    server.modify_system(system_id, 'hostname', opts['hostname'].value, token)

    if opts['bonding'].get_value():
	try:
            server.modify_system(system_id, 'modify_interface', {
            'macaddress-%s' % opts['eth_name1'].value       : opts['mac_addr1'].value,
            'bonding-%s' % opts['eth_name1'].value          : "slave",
            'bonding_master-%s' % opts['eth_name1'].value   : "bond0",
            'macaddress-%s' % opts['eth_name2'].value       : opts['mac_addr2'].value,
            'bonding-%s' % opts['eth_name2'].value          : "slave",
            'bonding_master-%s' % opts['eth_name2'].value   : "bond0",
            'ipaddress-bond0'                               : opts['ip_address'].value,
            'subnet-bond0'                                  : opts['subnet'].value,
            'bonding-bond0'                                 : "master",
            'static-bond0'                                  : True,
            'bonding_opts-bond0'                            : opts['bonding_opts'].value
            }, token)
        except xmlrpclib.Fault, f:
            return f.faultString
    else:
        try:
            server.modify_system(system_id,'modify_interface', {
            'macaddress-eth0'   : opts['mac_address'].value,
            'ipaddress-eth0'    : opts['ip_address'].value,
            'subnet-eth0'    : opts['subnet'].value,
            'static-eth0'    : True 
            }, token)
        except xmlrpclib.Fault, f:
            return f.faultString

    server.modify_system(system_id, 'gateway', opts['gateway'].value, token)
    server.modify_system(system_id, 'name_servers', opts['name_servers'].value, token)
    server.modify_system(system_id, 'name_servers_search', opts['name_servers_search'].value, token)

    if opts['profile'].value:
        server.modify_system(system_id, 'profile', opts['profile'].value, token)

    if opts['redhat_management_key'].value:
        server.modify_system(system_id, 'redhat_management_key', opts['redhat_management_key'].value, token)

    try:
        server.save_system(system_id, token)
    except xmlrpclib.Fault, f:
        return f.faultString

def generate_iso(systems, token):

    filename = os.path.dirname(__file__) + '/tmp/' + "".join(random.sample('qwertyui',8))+'.iso'
    options = {}
    options['iso'] = filename 
    options['profiles'] = '~'
    options['systems'] = systems

    try:
        status = server.background_buildiso(options, token)
	while 1:
	    if os.path.isfile(filename):
		break

	#Waiting for IO to settle.
        time.sleep(2)

        return filename
	
    except xmlrpclib.Fault, f:
        if f.faultCode == 1:
            raise web.seeother('/logout')
