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
from genie.libs.parser.utils import get_parser_exclude
from genie.utils.diff import Diff
from unicon.core.errors import ConnectionError
import os
from datetime import datetime
import time
import concurrent.futures
import sys
import re
from getpass import getpass


def make_connection(testbed_dict):  # testbed_dict: dict):

    global first_time_connection
    hostname = list(testbed_dict["devices"].keys())[0]
    testbed_nxos = testbed.load(testbed_dict)
    device = testbed_nxos.devices[hostname]
    if not device.is_connected():

        if first_time_connection:
            try:
                print(
                    "\nThe program is trying to connect to the {} {} device via {} port {}.".format(
                        testbed_dict["devices"][hostname]["ip"],
                        testbed_dict["devices"][hostname]["os"].upper(),
                        testbed_dict["devices"][hostname]["protocol"].upper(),
                        22,
                    )
                )
                device.connect(log_stdout=False, prompt_recovery=True)
                first_time_connection = False
            except ConnectionError:
                print("\nERROR: Can't establish the connection to the device.")
                print(
                    "Please check the hostname, IP aaddress, username, and password.\n"
                )
                sys.exit()
            # except:
            #     print("Somethings went wrong.")
            #     print("Unexpected error:", sys.exc_info()[0])
            #     sys.exit()
        else:
            print(
                "\nThe program is trying to connect to the {} {} device via {} port {}.".format(
                    testbed_dict["devices"][hostname]["ip"],
                    testbed_dict["devices"][hostname]["os"].upper(),
                    testbed_dict["devices"][hostname]["protocol"].upper(),
                    22,
                )
            )
            device.connect(log_stdout=False, prompt_recovery=True)

    return device


def learn_interface(device):

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

    return (num_intf_up, intf_up_list)


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


def learn_arp(device) -> dict:

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


def learn_routing(device: dict):

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


def parse_all_cmd(device):

    now1 = datetime.now()

    cmd_list = []
    cmd_error_list = []

    output1 = device.parse("all")

    for cmd in output1:
        if "errored" in output1[cmd].keys():
            cmd_error_list.append(cmd)
    for cmd_error in cmd_error_list:
        del output1[cmd_error]

    cmd_list = list(output1.keys())

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
        "---------------------------------------------------------------------------------------------------"
    )

    return output1, exclude


def learn_common(device):

    with concurrent.futures.ThreadPoolExecutor() as executor:

        intf_executor = executor.submit(learn_interface, device)
        mac_executor = executor.submit(learn_fdb, device)
        arp_executor = executor.submit(learn_arp, device)
        routes_executor = executor.submit(learn_routing, device)

        num_intf_up, intf_up_list = intf_executor.result()
        total_mac_address = mac_executor.result()
        arp_entries = arp_executor.result()
        num_routes = routes_executor.result()

    return num_intf_up, intf_up_list, total_mac_address, arp_entries, num_routes


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


def main():

    # declare global variables that are used by the main function
    global testbed_dict
    global have_original
    global is_detail
    global num_intf_up_original, intf_up_list_original, total_mac_address_original, arp_entries_original, num_routes_original
    global all_original

    # call make_connection to connect to the device. Passing the global testbed_dict variabl
    device = make_connection(testbed_dict)
    if device.is_connected():
        print("The device is connected.")

    # if the program have not capture the original snapshot, then it will do it.
    # if the main function is called again, then it would not re-capture the original snapshot.
    if not have_original:

        now1 = datetime.now()
        (
            num_intf_up_original,
            intf_up_list_original,
            total_mac_address_original,
            arp_entries_original,
            num_routes_original,
        ) = learn_common(device)

        now2 = datetime.now()

        print(
            "The common information for original state has learned in {} seconds.".format(
                (now2 - now1).total_seconds()
            )
        )
        print("The device is parsing all commands...")
        all_original, exclude = parse_all_cmd(device)
        print("The program has parsed all commands for original state.")

        have_original = True

    print("The programs is beginning to monitor.")

    # infinity while loop to keep monitor the device and compare with original snapshot
    while True:

        # learn the common information of device's after state
        (
            num_intf_up_after,
            intf_up_list_after,
            total_mac_address_after,
            arp_entries_after,
            num_routes_after,
        ) = learn_common(device)

        # find the delta between original and after state of device
        delta_intf = num_intf_up_original - num_intf_up_after
        delta_mac = total_mac_address_original - total_mac_address_after
        delta_arp = arp_entries_original - arp_entries_after
        delta_routes = num_routes_original - num_routes_after

        percentage_delta_intf = (delta_intf / num_intf_up_original) * 100
        percentage_delta_mac = (delta_mac / total_mac_address_original) * 100
        percentage_delta_arp = (delta_arp / arp_entries_original) * 100
        percentage_delta_routes = (delta_routes / num_routes_original) * 100

        if (
            len(intf_up_list_after) == len(intf_up_list_original)
            and percentage_delta_mac < lost_mac_safe
            and percentage_delta_arp < lost_arp_entries
            and percentage_delta_routes < lost_routes
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
                "There are {} ({}%) interfaces changed to down.".format(
                    delta_intf, percentage_delta_intf
                )
            )
            print("List of the interfaces changed to down:")
            for intf in intf_up_list_original:
                if intf not in intf_up_list_after:
                    print(intf)
            print()
            print(
                "There are {} ({}%) MAC addresses is lost.".format(
                    delta_mac, percentage_delta_mac
                )
            )

            print(
                "There are {} ({}%) ARP entries is lost.".format(
                    delta_arp, percentage_delta_arp
                )
            )

            print(
                "There are {} ({}%) routes is lost.".format(
                    delta_routes, percentage_delta_routes
                )
            )

        if is_detail:

            print("\nThe porgram is parsing all commands.")
            all_after, exclude = parse_all_cmd(device)

            print(
                "The program has parsed all commands. Please check the differences in all_diff.txt file."
            )
            diff = Diff(all_original, all_after, exclude=exclude)
            diff.findDiff()

            if not (str(diff) == ""):

                line_string = "\n------------------------------------------ {} --------------------------------------\n\n{}\n\n------------------------------------------------------------------------------------\n".format(
                    datetime.now().strftime("%Y-%b-%d %X"), diff
                )

            else:
                line_string = "\n------------------------------------------ {} --------------------------------------\n\n{}\n\n------------------------------------------------------------------------------------\n".format(
                    datetime.now().strftime("%Y-%b-%d %X"), "There is no change."
                )

            prepend_line("all_diff.txt", line_string)


def main_recursion():  # , testbed_dict):

    global have_original, is_detail

    try:
        main()  # , testbed_dict)
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

            main_recursion()

    except ConnectionError:
        print("\nThe connection is disconnected. The device may be reloading.")
        print("The program will try to re-connect after 30 seconds.\n")
        sleep(30)
        main_recursion()

    # except:
    #     print("Somethings went wrong.")
    #     print("Unexpected error:", sys.exc_info()[0])
    #     sys.exit()


if os.path.exists("./all_diff.txt"):
    os.remove("./all_diff.txt")

have_original = False
is_detail = False

num_intf_up_original = 0
intf_up_list_original = []
total_mac_address_original = 0
arp_entries_original = 0
num_routes_original = 0
all_original = {}
first_time_connection = True

hostname = input("Enter the hostname of the device: ")
ip = input("Enter the IP address of the device: ")
username = input("Enter username: ")
password = getpass()
lost_mac_safe = int(
    input("Enter the percentage lost of insignificant amount of MAC addresses: ")
)
lost_arp_entries = int(
    input("Enter the percentage lost of insignificant amount of ARP entries: ")
)
lost_routes = int(
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

main_recursion()
