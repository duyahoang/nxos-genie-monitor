#!/usr/bin/env python3
#
# Cisco System, Inc
# Author: Duy Hoang
# Mentors: Andy Jaramillo, Nathan Hemingway
# Project: Nexus Monitor Project
# Description: This is databaseconfig.py for the input information used by the nxos_monitor tool.
#
# Notice: The device name must match the hostname of the device, otherwise, the connection will hang.
#
# Examples:
#
# input_dict = {
#     "hostname": "router1"                     <--- need to be changed
#     "ip": "192.168.1.1",                      <--- need to be changed
#     "username": "admin",                      <--- need to be changed
#     "password": "Cisco",                      <--- need to be changed
# }
#
# lost_mac_safe = 30                            <--- need to be changed
# lost_arp_safe = 30                            <--- need to be changed
# lost_routes_safe = 5                          <--- need to be changed
#
# dir_output = "/home/script"                   <--- need to be changed
# dir_original_snapshot = "/home/script"        <--- need to be changed


input_dict = {
    "hostname": "something",
    "ip": "a.b.c.d",
    "username": "username",
    "password": "password",
}


# percentage
lost_mac_safe = 30
lost_arp_safe = 30
lost_routes_safe = 5

dir_output = "/home/script"

# Uncomment the line below to provide the directory of original snapshot. If not, the tool will learn the original state and save it in the dir_output.
# dir_original_snapshot = "/home/script"
