#!/usr/bin/env python3

# Cisco System, Inc
# Author: Duy Hoang
# Mentors: Andy Jaramillo, Nathan Hemingway
# Project: Nexus Monitor Project
# Description: The tool takes snapshot of the original operational state of the Nexus device including common information(interfaces, mac address, arp, and routing table)
# and parsing all show commands that are supported by the pyATS/Genie library. Then, the tool run infinity loop to capture the device's after state and compare with the original state to find the differences.
# The tool supports two modes. The first mode (default) is only compare the common information, and the second mode compares all show commands in after state and original state.
# Using Ctrl-C to pause the program to change the mode or exit the program.

# Requirement:
# python 3.8
# pip install genie[library]

from time import sleep
from genie import testbed
from genie.libs.ops.interface.nxos.interface import Interface
from genie.libs.ops.fdb.nxos.fdb import Fdb
from genie.libs.ops.routing.nxos.routing import Routing
from genie.libs.ops.vlan.nxos.vlan import Vlan
from genie.libs.ops.ospf.nxos.ospf import Ospf
from genie.libs.ops.bgp.nxos.bgp import Bgp
from genie.libs.parser.utils import get_parser_exclude
from genie.utils.diff import Diff
from unicon.core.errors import ConnectionError
import os
from datetime import datetime
import concurrent.futures
import sys
import re
from getpass import getpass
from pprint import pprint


def make_connection(testbed_dict):

    hostname = list(testbed_dict["devices"].keys())[0]
    testbed_nxos = testbed.load(testbed_dict)
    device = testbed_nxos.devices[hostname]

    if not device.is_connected():
        print(
            "\nThe program is trying to connect to the host {} {} {} device via {} port {}.".format(
                hostname,
                testbed_dict["devices"][hostname]["ip"],
                testbed_dict["devices"][hostname]["os"].upper(),
                testbed_dict["devices"][hostname]["protocol"].upper(),
                22,
            )
        )
        device.connect(log_stdout=False, prompt_recovery=True)

    return device


def learn_interface(device) -> list:

    num_intf_up = 0
    intf_up_list = []

    interface_object = Interface(device=device)
    interface_object.learn()

    for intf in interface_object.info:
        if (
            interface_object.info[intf].get("oper_status", None)
            and interface_object.info[intf]["oper_status"] == "up"
        ):
            intf_up_list.append(intf)
            num_intf_up = num_intf_up + 1

    # return (num_intf_up, intf_up_list)
    return intf_up_list


def learn_vlan(device) -> dict:

    vlan_object = Vlan(device=device)
    vlan_object.learn()
    if vlan_object.info.get("vlans", None):
        vlan_object.info["vlans"].pop("interface_vlan_enabled", None)
        vlan_object.info["vlans"].pop("vn_segment_vlan_based_enabled", None)
        vlan_object.info["vlans"].pop("configuration", None)

        return vlan_object.info["vlans"]
    else:
        return {}


def learn_fdb(device) -> int:

    total_mac_addresses = 0

    fdb_object = Fdb(device)
    fdb_object.learn()

    try:
        for key in fdb_object.info["mac_table"]["vlans"]:
            total_mac_addresses = total_mac_addresses + len(
                fdb_object.info["mac_table"]["vlans"][key]["mac_addresses"]
            )
        return total_mac_addresses
    except:
        return total_mac_addresses


def learn_arp(device) -> int:

    arp_entries = 0

    try:
        cmd = "show ip arp detail vrf all"
        arp_object_output = device.parse(cmd)

        if len(arp_object_output) < 1:
            return arp_entries
        if len(arp_object_output["interfaces"]) < 1:
            return arp_entries

        regex = r"^([0-9a-f]{4}[.]){2}([0-9a-f]{4})$"
        for key in arp_object_output["interfaces"]:
            for ip_key in arp_object_output["interfaces"][key]["ipv4"]["neighbors"]:
                if re.search(
                    regex,
                    arp_object_output["interfaces"][key]["ipv4"]["neighbors"][ip_key][
                        "link_layer_address"
                    ],
                ):
                    arp_entries = arp_entries + 1

    except ConnectionError:
        print("\nThe connection is disconnected. The device may be reloading.")

    except:
        print(
            "\nCannot parse the command: {}\nThe device may not support this command.\n".format(
                cmd
            )
        )

    return arp_entries


def learn_stp(device):

    stp_object_output = {}

    try:
        cmd = "show spanning-tree detail"
        stp_detail_output = device.parse(cmd)
        # if stp_detail_output is dict:
        #     stp_object_output.update(stp_detail_output)
    except:
        print(
            "\nCannot parse the command: {}\nThe device may not support this command.\n".format(
                cmd
            )
        )

    # pprint(stp_detail_output)

    # sys.exit()


def learn_routing(device) -> int:

    num_routes = 0

    routing_object = Routing(device=device)
    routing_object.learn()

    for vrf_key in routing_object.info["vrf"]:
        for ip_protocol_key in routing_object.info["vrf"][vrf_key]["address_family"]:
            num_routes = num_routes + len(
                routing_object.info["vrf"][vrf_key]["address_family"][ip_protocol_key][
                    "routes"
                ]
            )

    return num_routes


def learn_ospf(device) -> list:

    ospf_neighbor_list = []
    ospf_object = Ospf(device=device)
    ospf_object.learn()
    if ospf_object.info["feature_ospf"] == True and ospf_object.info.get("vrf", None):
        for vrf in list(ospf_object.info["vrf"].keys()):
            for instance in list(ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"].keys()):
                if ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance].get("areas", None):

                    for area in list(ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"].keys()):
                        if ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area].get("virtual_links", None):
                            for vLink in list(ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["virtual_links"].keys()):
                                if ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["virtual_links"][vLink].get("neighbors", None):
                                    for neighbor in list(ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["virtual_links"][vLink]["neighbors"].keys()):

                                        neighbor_dict = {
                                            "vrf": vrf,
                                            "ospf_instance": instance,
                                            "area": area,
                                            "virtual_link": vLink,
                                            "neighbor_router_id": ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["virtual_links"][vLink]["neighbors"][neighbor]["neighbor_router_id"],
                                            "neighbor_interface_address": ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["virtual_links"][vLink]["neighbors"][neighbor]["address"],
                                            "state": ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["virtual_links"][vLink]["neighbors"][neighbor]["state"]
                                        }

                                        ospf_neighbor_list.append(
                                            neighbor_dict)

                        if ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area].get("sham_links", None):
                            for slink in list(ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["sham_links"].keys()):
                                if ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["sham_links"][slink].get("neighbors", None):
                                    for neighbor in list(ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["sham_links"][slink]["neighbors"].keys()):

                                        neighbor_dict = {
                                            "vrf": vrf,
                                            "ospf_instance": instance,
                                            "area": area,
                                            "sham_link": slink,
                                            "neighbor_router_id": ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["sham_links"][slink]["neighbors"][neighbor]["neighbor_router_id"],
                                            "neighbor_interface_address": ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["sham_links"][slink]["neighbors"][neighbor]["address"],
                                            "state": ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["sham_links"][slink]["neighbors"][neighbor]["state"]
                                        }

                                        ospf_neighbor_list.append(
                                            neighbor_dict)

                        if ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area].get("interfaces", None):
                            for interface in list(ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["interfaces"].keys()):
                                if ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["interfaces"][interface].get("neighbors", None):
                                    for neighbor in list(ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["interfaces"][interface]["neighbors"].keys()):

                                        neighbor_dict = {
                                            "vrf": vrf,
                                            "ospf_instance": instance,
                                            "area": area,
                                            "interface": interface,
                                            "neighbor_router_id": ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["interfaces"][interface]["neighbors"][neighbor]["neighbor_router_id"],
                                            "neighbor_interface_address": ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["interfaces"][interface]["neighbors"][neighbor]["address"],
                                            "state": ospf_object.info["vrf"][vrf]["address_family"]["ipv4"]["instance"][instance]["areas"][area]["interfaces"][interface]["neighbors"][neighbor]["state"]
                                        }

                                        ospf_neighbor_list.append(
                                            neighbor_dict)

    return ospf_neighbor_list


def parse_all_cmd(device):

    now1 = datetime.now()

    cmd_list = []
    cmd_error_list = []

    output = device.parse("all")

    for cmd in output:
        if "errored" in output[cmd].keys():
            cmd_error_list.append(cmd)
    for cmd_error in cmd_error_list:
        del output[cmd_error]

    cmd_list = list(output.keys())

    for i in range(len(cmd_list)):
        if i == 0:
            exclude = get_parser_exclude(cmd_list[i], device)
        else:
            exclude.extend(get_parser_exclude(cmd_list[i], device))

    exclude.extend(
        [
            "idle_percent",
            "kernel_percent",
            "user_percent",
            "bpdu_sent",
            "time_since_topology_change",
            "show users",
            "current_temp_celsius",
            "fwd_id",
            "table_id",
            "vrf_id ",
            "counters",
        ]
    )

    now2 = datetime.now()
    seconds = (now2 - now1).total_seconds()
    print(
        "----------------------------------- {} --------------------------------------".format(
            datetime.now().strftime("%Y-%b-%d %X")
        )
    )
    print("The program has parsed all commands in {} seconds.".format(seconds))
    print(
        "-----------------------------------------------------------------------------------------------"
    )

    return output, exclude


def learn_common(device) -> tuple:

    with concurrent.futures.ThreadPoolExecutor() as executor:

        intf_executor = executor.submit(learn_interface, device)
        vlan_executor = executor.submit(learn_vlan, device)
        mac_executor = executor.submit(learn_fdb, device)
        arp_executor = executor.submit(learn_arp, device)
        stp_executor = executor.submit(learn_stp, device)
        routes_executor = executor.submit(learn_routing, device)
        ospf_executor = executor.submit(learn_ospf, device)

        intf_up_list = intf_executor.result()
        vlan_dict = vlan_executor.result()
        total_mac_address = mac_executor.result()
        arp_entries = arp_executor.result()
        stp_none = stp_executor.result()
        num_routes = routes_executor.result()
        ospf_neighbor_list = ospf_executor.result()

    return (
        intf_up_list,
        vlan_dict,
        total_mac_address,
        arp_entries,
        num_routes,
        ospf_neighbor_list,
    )


def prepend_line(file_name, line):
    """Insert given string as a new line at the beginning of a file"""

    if not os.path.exists("./{}".format(file_name)):
        with open(file_name, "w") as write_obj:
            write_obj.write(line + "\n")
    else:
        # define name of temporary dummy file
        dummy_file = file_name + ".bak"
        # open original file in read mode and dummy file in write mode
        with open(file_name, "r") as read_obj, open(dummy_file, "w") as write_obj:
            # Write given line to the dummy file
            write_obj.write(line + "\n")
            # Read lines from original file one by one and append them to the dummy file
            for line in read_obj:
                write_obj.write(line)
        # remove original file
        os.remove(file_name)
        # Rename dummy file as the original file
        os.rename(dummy_file, file_name)


def find_interfaces_down(intf_up_list_original: list, intf_up_list_after: list) -> tuple:

    intf_down_list = []
    for intf in intf_up_list_original:
        if intf not in intf_up_list_after:
            intf_down_list.append(intf)

    delta_intf = len(intf_down_list)
    percentage_delta_intf = (len(intf_down_list) /
                             len(intf_up_list_original)) * 100

    return (intf_down_list, delta_intf, percentage_delta_intf)


def find_vlans_change(vlan_dict_original: dict, vlan_dict_after: dict) -> tuple:

    vlan_change_list = []
    if len(vlan_dict_original) > 0:
        for vlan_original in list(vlan_dict_original.keys()):
            if vlan_dict_original[vlan_original]["state"] != "active":
                continue
            else:
                if vlan_original in list(vlan_dict_after.keys()):
                    if vlan_dict_after[vlan_original]["state"] != "active":
                        vlan_change_list.append(
                            {vlan_original: vlan_dict_after[vlan_original]}
                        )
                else:
                    vlan_change_list.append(
                        {vlan_original: {"state": "Not found in VLAN database"}}
                    )

        delta_vlan = len(vlan_change_list)
        percentage_delta_vlan = (
            len(vlan_change_list) / len(vlan_dict_original)) * 100

    return (vlan_change_list, delta_vlan, percentage_delta_vlan)


def find_ospf_neighbors_change(ospf_neighbor_list_original: list, ospf_neighbor_list_after: list) -> tuple:

    neighbor_change_list = []
    for neighbor_original in ospf_neighbor_list_original:
        if neighbor_original["state"] != "full":
            continue
        else:
            count = 0
            for neighbor_after in ospf_neighbor_list_after:
                if (
                    neighbor_after["vrf"] == neighbor_original["vrf"]
                    and neighbor_after["ospf_instance"]
                    == neighbor_original["ospf_instance"]
                    and neighbor_after["area"] == neighbor_original["area"]
                    and neighbor_after["neighbor_router_id"]
                    == neighbor_original["neighbor_router_id"]
                ):

                    if (
                        neighbor_after.get("virtual_link", None)
                        and neighbor_after["virtual_link"]
                        == neighbor_original["virtual_link"]
                    ):
                        if neighbor_after["state"] != "full":
                            neighbor_change_list.append(neighbor_after)
                        break

                    elif (
                        neighbor_after.get("sham_link", None)
                        and neighbor_after["sham_link"]
                        == neighbor_original["sham_link"]
                    ):
                        if neighbor_after["state"] != "full":
                            neighbor_change_list.append(neighbor_after)
                        break

                    elif (
                        neighbor_after.get("interface", None)
                        and neighbor_after["interface"]
                        == neighbor_original["interface"]
                    ):
                        if neighbor_after["state"] != "full":
                            neighbor_change_list.append(neighbor_after)
                        break

                    count = 0
                    continue
                else:
                    count = count + 1

            if count == len(ospf_neighbor_list_after):
                neighbor_lost = {}
                for key, value in neighbor_original.items():
                    if key == "state":
                        neighbor_lost["state"] = "Not found in OSPF neighbor table"
                    else:
                        neighbor_lost[key] = value
                neighbor_change_list.append(neighbor_lost)

    delta_ospf = len(neighbor_change_list)
    percentage_delta_ospf = (
        len(neighbor_change_list) / len(ospf_neighbor_list_original)
    ) * 100

    return (neighbor_change_list, delta_ospf, percentage_delta_ospf)


def get_testbed() -> tuple:

    print()

    try:
        if os.path.exists("./databaseconfig.py"):
            print("Found {}/databaseconfig.py".format(os.path.abspath(os.getcwd())))

        import databaseconfig as cfg

        print("Imported databaseconfig.py file successfully.")
        testbed_dict = cfg.testbed_dict
        lost_mac_safe = cfg.lost_mac_safe
        lost_arp_safe = cfg.lost_arp_safe
        lost_routes_safe = cfg.lost_routes_safe
    except:

        print(
            "Cannot find or import {}/databaseconfig.py\n".format(
                os.path.abspath(os.getcwd())
            )
        )
        hostname = input("Enter the hostname of the device: ")
        ip = input("Enter the IP address of the device: ")
        username = input("Enter username: ")
        password = getpass()
        lost_mac_safe = int(
            input(
                "Enter the percentage lost of insignificant amount of MAC addresses: "
            )
        )
        lost_arp_safe = int(
            input("Enter the percentage lost of insignificant amount of ARP entries: ")
        )
        lost_routes_safe = int(
            input(
                "Enter the percentage lost of insignificant amount of routes in routing table: "
            )
        )
        testbed_dict = {
            "devices": {
                hostname: {
                    "ip": ip,
                    "protocol": "ssh",
                    "username": username,
                    "password": password,
                    "os": "nxos",
                },
            }
        }

    lost_safe_tuple = (lost_mac_safe, lost_arp_safe, lost_routes_safe)

    return (testbed_dict, lost_safe_tuple)


def find_delta(original, after) -> tuple:

    delta = 0
    percentage_delta_mac = 0

    if original != 0:
        delta = original - after
        percentage_delta_mac = (delta / original) * 100

    return (delta, percentage_delta_mac)


def main():

    testbed_dict, lost_safe_tuple = get_testbed()

    # first connection
    try:
        device = make_connection(testbed_dict)
    except ConnectionError:
        print("\nERROR: Can't establish the connection to the device.")
        print("Please check the hostname, IP aaddress, username, and password.\n")
        sys.exit()
    if device.is_connected():
        print("The device is connected.")
    # except:
    #     print("Somethings went wrong.")
    #     print("Unexpected error:", sys.exc_info()[0])
    #     sys.exit()

    if os.path.exists("./all_diff.txt"):
        os.remove("./all_diff.txt")

    have_original = False
    is_detail = False

    try:

        # take original snapshot
        print("The program is learning device's common information original state...")
        now1 = datetime.now()
        (
            intf_up_list_original,
            vlan_dict_original,
            total_mac_address_original,
            arp_entries_original,
            num_routes_original,
            ospf_neighbor_list_original,
        ) = learn_common(device)

        now2 = datetime.now()

        print(
            "The common information for original state has learned in {:.2f} seconds.".format(
                (now2 - now1).total_seconds()
            )
        )
        print("The device is parsing all commands...")
        all_original, exclude = parse_all_cmd(device)
        print("The program has parsed all commands for original state.")

        original_snapshot = (
            intf_up_list_original,
            vlan_dict_original,
            total_mac_address_original,
            arp_entries_original,
            num_routes_original,
            ospf_neighbor_list_original,
            all_original,
            exclude,
        )

        have_original = True

    except KeyboardInterrupt:
        print("\nThe program has exited before learning device's original state.\n")
        sys.exit()
    except ConnectionError:
        print(
            "\nThe connection to device has been disconnected before learning device's original state.\n"
        )
        sys.exit()
    # except:
    #     print("Somethings went wrong.")
    #     print("Unexpected error:", sys.exc_info()[0])
    #     sys.exit()
    # change mode

    while True:
        have_original, is_detail = change_mode(
            have_original,
            device,
            testbed_dict,
            is_detail,
            lost_safe_tuple,
            original_snapshot,
        )


def monitor(device, testbed_dict, is_detail, lost_safe_tuple, original_snapshot):

    # check if device is connected
    if device.is_connected():
        print("The device is connected.")
    else:
        device = make_connection(testbed_dict)

    # unpack lost_safe_tuple
    lost_mac_safe, lost_arp_safe, lost_routes_safe = lost_safe_tuple

    # unpack original snapshot
    (
        intf_up_list_original,
        vlan_dict_original,
        total_mac_address_original,
        arp_entries_original,
        num_routes_original,
        ospf_neighbor_list_original,
        all_original,
        exclude,
    ) = original_snapshot

    print("The programs is beginning to monitor...")

    # infinity while loop to keep monitor the device and compare with original snapshot
    while True:

        # learn the common information of device's after state
        (
            intf_up_list_after,
            vlan_dict_after,
            total_mac_address_after,
            arp_entries_after,
            num_routes_after,
            ospf_neighbor_list_after,
        ) = learn_common(device)

        # find the delta between original and after state of device
        delta_mac, percentage_delta_mac = find_delta(
            total_mac_address_original, total_mac_address_after)
        delta_arp, percentage_delta_arp = find_delta(
            arp_entries_original, arp_entries_after)
        delta_routes, percentage_delta_routes = find_delta(
            num_routes_original, num_routes_after)

        # find interface changed to down
        intf_down_list, delta_intf, percentage_delta_intf = find_interfaces_down(
            intf_up_list_original, intf_up_list_after
        )

        # find vlan changed
        vlan_change_list, delta_vlan, percentage_delta_vlan = find_vlans_change(
            vlan_dict_original, vlan_dict_after
        )

        # find OSPF neighbor changed
        (
            neighbor_change_list,
            delta_ospf,
            percentage_delta_ospf,
        ) = find_ospf_neighbors_change(
            ospf_neighbor_list_original, ospf_neighbor_list_after
        )

        if (
            len(intf_down_list) == 0
            and len(vlan_change_list) == 0
            and len(neighbor_change_list) == 0
            and percentage_delta_mac < lost_mac_safe
            and percentage_delta_arp < lost_arp_safe
            and percentage_delta_routes < lost_routes_safe
        ):
            print(
                "\n---------------------------------- {} --------------------------------------".format(
                    datetime.now().strftime("%Y-%b-%d %X")
                )
            )
            print("There is no change in common information.")
        else:
            print(
                "\n---------------------------------- {} --------------------------------------".format(
                    datetime.now().strftime("%Y-%b-%d %X")
                )
            )

            print(
                "There are {} ({:.2f}%) interfaces changed to down.".format(
                    delta_intf, percentage_delta_intf
                )
            )
            print("List of the interfaces changed to down:")
            for intf in intf_down_list:
                print(intf)
            print()

            print(
                "There are {} ({:.2f}%) vlans changed.".format(
                    delta_vlan, percentage_delta_vlan
                )
            )
            print("List of the vlans changed to down:")
            for vlan_dict in vlan_change_list:
                vlan = list(vlan_dict.keys())[0]
                state = vlan_dict[vlan]["state"]
                print("VLAN {} - state: {}".format(vlan, state))
            print()

            print(
                "There are {} ({:.2f}%) OSPF neighbors' state have been changed.".format(
                    delta_ospf, percentage_delta_ospf
                )
            )
            print("List of the OSPF neighbors' state have been changed: ")
            for neighbor_dict in neighbor_change_list:
                pprint(neighbor_dict)
            print()

            print(
                "There are {} ({:.2f}%) MAC addresses is lost.".format(
                    delta_mac, percentage_delta_mac
                )
            )

            print(
                "There are {} ({:.2f}%) ARP entries is lost.".format(
                    delta_arp, percentage_delta_arp
                )
            )

            print(
                "There are {} ({:.2f}%) routes is lost.".format(
                    delta_routes, percentage_delta_routes
                )
            )
        print()

        if is_detail:

            print("\nThe porgram is parsing all commands.")
            all_after, exclude = parse_all_cmd(device)

            print(
                "The program has parsed all commands. Please check the differences in all_diff.txt file."
            )
            diff = Diff(all_original, all_after, exclude=exclude)
            diff.findDiff()

            if not (str(diff) == ""):

                line_string = "\n------------------------------------------ {} --------------------------------------\n\n{}\n\n------------------------------------------------------------------------------------------------------\n".format(
                    datetime.now().strftime("%Y-%b-%d %X"), diff
                )

            else:
                line_string = "\n------------------------------------------ {} --------------------------------------\n\n{}\n\n------------------------------------------------------------------------------------------------------\n".format(
                    datetime.now().strftime("%Y-%b-%d %X"), "There is no change."
                )

            prepend_line("all_diff.txt", line_string)
        print(
            "-----------------------------------------------------------------------------------------------"
        )


def change_mode(
    have_original, device, testbed_dict, is_detail, lost_safe_tuple, original_snapshot
):

    try:
        monitor(device, testbed_dict, is_detail,
                lost_safe_tuple, original_snapshot)
    except KeyboardInterrupt:

        if not have_original:
            print("\nThe program has exited.\n")
            sys.exit()
        else:

            print("\nYou have paused the program.\n")

            exit = input("\nDo you want to exit the program? (Y or N)? ")

            while exit.upper() != "Y" and exit.upper() != "N":
                print("Your input is invalid. Please enter Y or N.")
                exit = input("\nDo you want to exit the program? (Y or N)? ")
            if exit.upper() == "Y":
                print("\nThe program has exited.\n")
                sys.exit()

            if is_detail:
                off_detail_input = input(
                    "\nDo you want to turn off the mode compare all detail differences (Y or N)? "
                )
                while (
                    off_detail_input.upper() != "Y" and off_detail_input.upper() != "N"
                ):
                    print("Your input is invalid. Please enter Y or N.")
                    off_detail_input = input(
                        "\nDo you want to turn off the mode compare all detail differences (Y or N)? "
                    )
                if off_detail_input.upper() == "Y":
                    is_detail = False
                else:
                    is_detail = True
            else:
                on_detail_input = input(
                    "\nDo you want to turn on the mode compare all detail differences (Y or N)? "
                )
                while on_detail_input.upper() != "Y" and on_detail_input.upper() != "N":
                    print("Your input is invalid. Please enter Y or N.")
                    on_detail_input = input(
                        "\nDo you want to turn on the mode compare all detail differences (Y or N)? "
                    )
                if on_detail_input.upper() == "Y":
                    is_detail = True
                else:
                    is_detail = False

    except ConnectionError:
        print("\nThe connection is disconnected. The device may be reloading.")
        print("The program will try to re-connect after 30 seconds.\n")
        sleep(30)

    # except:
    #     print("Somethings went wrong.")
    #     print("Unexpected error:", sys.exc_info()[0])
    #     sys.exit()

    return have_original, is_detail


if __name__ == "__main__":
    main()
