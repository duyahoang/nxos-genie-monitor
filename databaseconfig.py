#!/usr/bin/env python3
#
# Cisco System, Inc
# Author: Duy Hoang
# Mentors: Andy Jaramillo, Nathan Hemingway
# Project: Nexus Monitor Project
# Description: This is databaseconfig.py for the input information used by the nxos_monitor tool.
#
# Examples:
# testbed_dict = {
#     "router1": {
#         "hostname": {
#             "ip": "192.168.1.1",
#             "protocol": "ssh",
#             "username": "admin",
#             "password": "Cisco",
#             "os": "nxos",
#         },
#     }
# }

# lost_mac_safe = 30
# lost_arp_safe = 30
# lost_routes_safe = 5

# dir_output = "/home/script"

testbed_dict = {
    "devices": {
        "hostname": {
            "ip": "a.b.c.d",
            "protocol": "ssh",
            "username": "username",
            "password": "password",
            "os": "nxos",
        },
    }
}


# percentage
lost_mac_safe = 30
lost_arp_safe = 30
lost_routes_safe = 5

dir_output = "/home/script"
