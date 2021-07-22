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
# python 3.6
# pip install pyats[library]


from genie import testbed
from genie.ops.utils import get_ops
from genie import parsergen
from genie.libs.parser.utils import get_parser_exclude
from genie.utils.diff import Diff
from unicon.core.errors import ConnectionError
import os
from datetime import datetime
from time import sleep
import concurrent.futures
import sys
import re
from getpass import getpass
import json
from pprint import pprint


class_list = list()
unsupport_list = list()
lost_mac_safe = 0
lost_arp_safe = 0
lost_routes_safe = 0
have_original_dir = False
dir_original_snapshot_import = str()
dir_original_snapshot_create = str()


def decorator_instance(class_monitor):
    class_list.append(class_monitor)
    return class_monitor


class Device:
    def __init__(self, testbed_dict) -> None:
        self.testbed_dict = testbed_dict
        hostname = list(self.testbed_dict["devices"].keys())[0]
        testbed_nxos = testbed.load(self.testbed_dict)
        self.device = testbed_nxos.devices[hostname]

    def make_connection(self):

        if not self.device.is_connected():
            print(
                "\nThe program is trying to connect to the host {} {} {} device via line VTY {} port {}.".format(
                    self.device.name,
                    self.testbed_dict["devices"][self.device.name]["connections"]["vty"]["ip"],
                    self.testbed_dict["devices"][self.device.name]["os"].upper(
                    ),
                    self.testbed_dict["devices"][self.device.name]["connections"]["vty"]["protocol"].upper(
                    ),
                    22,
                )
            )
            self.device.connect(log_stdout=False, prompt_recovery=True)
            # self.device.connect(via="vty", pool_size=10, log_stdout=False, prompt_recovery=True)


@decorator_instance
class InterfaceMonitor:

    def __init__(self, device):

        self.device = device

    def learn_interfaces(self) -> list:

        num_intf_up = 0
        intf_up_list = []
        try:
            Interface = get_ops('interface', self.device)
            interface_object = Interface(device=self.device)
            interface_object.learn()

            for intf in interface_object.info:
                if (
                    interface_object.info[intf].get("oper_status", None)
                    and interface_object.info[intf]["oper_status"] == "up"
                ):
                    intf_up_list.append(intf)
                    num_intf_up = num_intf_up + 1

            return intf_up_list

        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except ConnectionError:
            raise ConnectionError
        except:
            unsupport_list.append("InterfaceMonitor_instance")
            print("Cannot monitor interfaces.")
            return intf_up_list

    def original(self):

        if not have_original_dir:
            self.intf_up_list_original = self.learn_interfaces()
            with open("{}/interface_up_list.json".format(dir_original_snapshot_create), 'w') as f:
                f.write(json.dumps(self.intf_up_list_original, indent=4))

        else:
            try:
                if os.path.isfile("{}/interface_up_list.json".format(dir_original_snapshot_import)):
                    with open("{}/interface_up_list.json".format(dir_original_snapshot_import), 'r') as f:
                        self.intf_up_list_original = json.load(f)
                else:
                    unsupport_list.append("InterfaceMonitor_instance")
            except:
                unsupport_list.append("InterfaceMonitor_instance")

    def current(self):

        if hasattr(self, "intf_up_list_original"):
            self.intf_up_list_current = self.learn_interfaces()
            self.intf_down_list, self.delta_intf, self.percentage_delta_intf = self.__find_interfaces_down()
            return None
        else:
            print("The original interfaces of {} have not been learned yet. Therefore, please learn the original interfaces before learning the current.".format(
                self.device.hostname))
            return None

    def __find_interfaces_down(self) -> tuple:

        intf_down_list = []
        for intf in self.intf_up_list_original:
            if intf not in self.intf_up_list_current:
                intf_down_list.append(intf)

        delta_intf = len(intf_down_list)
        percentage_delta_intf = (len(intf_down_list) /
                                 len(self.intf_up_list_original)) * 100

        return (intf_down_list, delta_intf, percentage_delta_intf)

    def is_changed(self):
        if hasattr(self, "intf_down_list"):
            if len(self.intf_down_list) > 0:
                return True
            else:
                return False
        else:
            return False

    def diff(self):
        if hasattr(self, "intf_down_list") and hasattr(self, "delta_intf") and hasattr(self, "percentage_delta_intf"):
            string = "List of the interfaces changed to down:\n"
            if len(self.intf_down_list) > 0:
                for intf in self.intf_down_list:
                    string = string + "   {}\n".format(intf)
                return string
            else:
                string = string + "   None\n"
                return string
        else:
            return None


@decorator_instance
class FabricpathMonitor:
    # __init__ need to have two arguments. The device will be passed when create an instance.
    def __init__(self, device) -> None:
        self.device = device

    def learn_fabricpath(self):

        fabricpath_adjacency_dict = dict()

        try:
            cmd = "show fabricpath isis adjacency"
            output = self.device.parse(cmd)

            if len(output) < 1:
                return fabricpath_adjacency_dict
            if len(output["domain"]) < 1:
                return fabricpath_adjacency_dict

            # regex = r"^([0-9a-f]{4}[.]){2}([0-9a-f]{4})$"
            for key in output["domain"]:
                if "interfaces" in output["domain"][key].keys():
                    for inside_key in output["domain"][key]["interfaces"]:
                        if output["domain"][key]["interfaces"][inside_key]["state"].lower() == "up":
                            fabricpath_adjacency_dict[inside_key] = output["domain"][key]["interfaces"][inside_key]

            return fabricpath_adjacency_dict

        except ConnectionError:
            print("\nThe connection is disconnected. The device may be reloading.")
            raise ConnectionError
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            print(
                "\nCannot parse the command: {}\nThe device may not support this command.\nCannot monitor fabricpath.\n".format(
                    cmd
                )
            )
            unsupport_list.append("FabricpathMonitor_instance")

        return fabricpath_adjacency_dict

    def original(self) -> None:

        if not have_original_dir:
            self.fabricpath_adjacency_dict_original = self.learn_fabricpath()
            with open("{}/fabricpath_adjacency_dict.json".format(dir_original_snapshot_create), 'w') as f:
                f.write(json.dumps(
                    self.fabricpath_adjacency_dict_original, indent=4))

        else:
            try:
                if os.path.isfile("{}/fabricpath_adjacency_dict.json".format(dir_original_snapshot_import)):

                    with open("{}/fabricpath_adjacency_dict.json".format(dir_original_snapshot_import), 'r') as f:
                        self.fabricpath_adjacency_dict_original = json.load(f)
                else:
                    unsupport_list.append("FabricpathMonitor_instance")
            except:
                unsupport_list.append("FabricpathMonitor_instance")

    def current(self) -> None:

        if hasattr(self, "fabricpath_adjacency_dict_original"):
            self.fabricpath_adjacency_dict_current = self.learn_fabricpath()
            self.fabricpath_down_list, self.delta_fabricpath, self.percentage_delta_fabricpath = self.__fabricpath_down_list()
            return None
        else:
            print("The original fabricpath of {} have not been learned yet. Therefore, please learn the original fabricpath before learning the current.".format(
                self.device.hostname))
            return None

    def __find_fabricpath_down(self):
        fabricpath_down_list = []
        for key, value in self.fabricpath_adjacency_dict_original:
            if key not in self.fabricpath_adjacency_dict_current.keys():
                fabricpath_down_list.append({key: value})

        delta_fabricpath = len(fabricpath_down_list)
        percentage_delta_fabricpath = (len(fabricpath_down_list) /
                                       len(self.fabricpath_adjacency_dict_original)) * 100

        return (fabricpath_down_list, delta_fabricpath, percentage_delta_fabricpath)

    def is_changed(self) -> bool:

        if hasattr(self, "fabricpath_down_list"):
            if len(self.fabricpath_down_list) > 0:
                return True
            else:
                return False
        else:
            return False

    def diff(self) -> str:

        if hasattr(self, "fabricpath_down_list") and hasattr(self, "delta_fabricpath") and hasattr(self, "percentage_delta_fabricpath"):
            string = "There are {} ({}%) fabricpath changed to down.\nList of the fabricpath changed to down:\n".format(
                self.delta_fabricpath, self.percentage_delta_fabricpath)
            if len(self.fabricpath_down_list) > 0:
                for data in self.fabricpath_down_list:
                    string = string + "\n   {}\n".format(data.keys()[0])
                    for value in data.values():
                        string = string + "      {}\n".format(value)

                return string
            else:
                string = string + "   None\n"
                return string
        else:
            return None


@decorator_instance
class VlanMonitor:

    def __init__(self, device):

        self.device = device

    def learn_vlans(self) -> dict:

        try:
            Vlan = get_ops('vlan', self.device)
            vlan_object = Vlan(device=self.device)
            vlan_object.learn()

            if vlan_object.info.get("vlans", None):
                vlan_object.info["vlans"].pop("interface_vlan_enabled", None)
                vlan_object.info["vlans"].pop(
                    "vn_segment_vlan_based_enabled", None)
                vlan_object.info["vlans"].pop("configuration", None)

                vlan_dict = dict(vlan_object.info["vlans"])

                return vlan_dict
            else:
                return {}
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except ConnectionError:
            raise ConnectionError
        except:
            unsupport_list.append("VlanMonitor_instance")
            print("Cannot monitor VLANs.")
            return {}

    def original(self):

        if not have_original_dir:

            self.vlan_dict_original = self.learn_vlans()

            with open("{}/vlan.json".format(dir_original_snapshot_create), 'w') as f:
                f.write(json.dumps(self.vlan_dict_original, indent=4))

        else:
            try:
                if os.path.isfile("{}/vlan.json".format(dir_original_snapshot_import)):
                    with open("{}/vlan.json".format(dir_original_snapshot_import), 'r') as f:
                        self.vlan_dict_original = json.load(f)
                else:
                    unsupport_list.append("VlanMonitor_instance")
            except:
                unsupport_list.append("VlanMonitor_instance")

    def current(self):
        if hasattr(self, "vlan_dict_original"):
            self.vlan_dict_current = self.learn_vlans()
            self.vlan_change_list, self.delta_vlan, self.percentage_delta_vlan = self.__find_vlans_change()
            return None
        else:
            print("The original VLANs of {} have not been learned yet. Therefore, please learn the original VLANs before learning the current.".format(
                self.device.hostname))
            return None

    def __find_vlans_change(self) -> tuple:

        vlan_change_list = []
        if len(self.vlan_dict_original) > 0:
            for vlan_original in list(self.vlan_dict_original.keys()):
                if self.vlan_dict_original[vlan_original]["state"] != "active":
                    continue
                else:
                    if vlan_original in list(self.vlan_dict_current.keys()):
                        if self.vlan_dict_current[vlan_original]["state"] != "active":
                            vlan_change_list.append(
                                {vlan_original:
                                    self.vlan_dict_current[vlan_original]}
                            )
                    else:
                        vlan_change_list.append(
                            {vlan_original: {"state": "Not found in VLAN database"}}
                        )

            delta_vlan = len(vlan_change_list)
            percentage_delta_vlan = (
                len(vlan_change_list) / len(self.vlan_dict_original)) * 100

        return (vlan_change_list, delta_vlan, percentage_delta_vlan)

    def is_changed(self):
        if hasattr(self, "vlan_change_list"):
            if len(self.vlan_change_list) > 0:
                return True
            else:
                return False
        else:
            return False

    def diff(self):
        if hasattr(self, "vlan_change_list") and hasattr(self, "delta_vlan") and hasattr(self, "percentage_delta_vlan"):
            string = "List of the vlans changed to down:\n"
            if len(self.vlan_change_list) > 0:
                for vlan_dict in self.vlan_change_list:
                    vlan = list(vlan_dict.keys())[0]
                    state = vlan_dict[vlan]["state"]
                    string = string + \
                        "   VLAN {} - state: {}\n".format(vlan, state)
                return string
            else:
                string = string + "   None\n"
                return string
        else:
            return None


@decorator_instance
class FdbMonitor:

    def __init__(self, device):

        self.device = device

    def learn_fdb(self) -> int:

        total_mac_addresses = 0
        try:
            Fdb = get_ops('fdb', self.device)
            fdb_object = Fdb(self.device)
            fdb_object.learn()

            try:
                for key in fdb_object.info["mac_table"]["vlans"]:
                    total_mac_addresses = total_mac_addresses + len(
                        fdb_object.info["mac_table"]["vlans"][key]["mac_addresses"]
                    )

                return total_mac_addresses

            except:
                return total_mac_addresses
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except ConnectionError:
            raise ConnectionError
        except:
            unsupport_list.append("FdbMonitor_instance")
            print("Cannot monitor MAC address table.")
            return total_mac_addresses

    def original(self):

        if not have_original_dir:

            self.total_mac_addresses_original = self.learn_fdb()
            fdb_dict = dict()
            fdb_dict["total_mac_addresses_original"] = self.total_mac_addresses_original
            with open("{}/fdb.json".format(dir_original_snapshot_create), 'w') as f:
                f.write(json.dumps(fdb_dict, indent=4))

        else:
            try:
                if os.path.isfile("{}/fdb.json".format(dir_original_snapshot_import)):
                    with open("{}/fdb.json".format(dir_original_snapshot_import), 'r') as f:
                        fdb_dict = json.load(f)
                        self.total_mac_addresses_original = fdb_dict["total_mac_addresses_original"]
                else:
                    unsupport_list.append("FdbMonitor_instance")
            except:
                unsupport_list.append("FdbMonitor_instance")

    def current(self):
        if hasattr(self, "total_mac_addresses_original"):
            self.total_mac_addresses_current = self.learn_fdb()
            self.delta_mac, self.percentage_delta_mac = self.__find_delta()
            return None
        else:
            print("The original FDB - MAC Address table of {} have not been learned yet. Therefore, please learn the original FDB - MAC Address table before learning the current.".format(
                self.device.hostname))
            return None

    def __find_delta(self) -> tuple:

        delta_mac = 0
        percentage_delta_mac = 0

        if self.total_mac_addresses_original != 0:
            delta_mac = self.total_mac_addresses_original - self.total_mac_addresses_current
            percentage_delta_mac = (
                delta_mac / self.total_mac_addresses_original) * 100

        return (delta_mac, percentage_delta_mac)

    def is_changed(self):
        if hasattr(self, "delta_mac") and hasattr(self, "percentage_delta_mac"):
            if self.percentage_delta_mac > lost_mac_safe:
                return True
            else:
                return False
        else:
            return False

    def diff(self):
        if hasattr(self, "delta_mac") and hasattr(self, "percentage_delta_mac"):

            string = "There are {} ({:.2f}%) MAC addresses is lost.".format(
                self.delta_mac, self.percentage_delta_mac
            )
            string = string + "\n"
            return string
        else:
            return None


@decorator_instance
class ArpMonitor:

    def __init__(self, device):

        self.device = device

    def learn_arp(self) -> int:

        arp_entries = 0

        try:
            cmd = "show ip arp detail vrf all"
            arp_object_output = self.device.parse(cmd)

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
            raise ConnectionError
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            print(
                "\nCannot parse the command: {}\nThe device may not support this command.\nCannot monitor ARP table.\n".format(
                    cmd
                )
            )
            unsupport_list.append("ArpMonitor_instance")

        return arp_entries

    def original(self):

        if not have_original_dir:

            self.arp_entries_original = self.learn_arp()
            arp_dict = dict()
            arp_dict["total_arp_entries_original"] = self.arp_entries_original
            with open("{}/arp.json".format(dir_original_snapshot_create), 'w') as f:
                f.write(json.dumps(arp_dict, indent=4))

        else:
            try:
                if os.path.isfile("{}/arp.json".format(dir_original_snapshot_import)):
                    with open("{}/arp.json".format(dir_original_snapshot_import), 'r') as f:
                        arp_dict = json.load(f)
                        self.arp_entries_original = arp_dict["total_arp_entries_original"]
                else:
                    unsupport_list.append("ArpMonitor_instance")
            except:
                unsupport_list.append("ArpMonitor_instance")

    def current(self):
        if hasattr(self, "arp_entries_original"):
            self.arp_entries_current = self.learn_arp()
            self.delta_arp, self.percentage_delta_arp = self.__find_delta()
            return None
        else:
            print("The original ARP table of {} have not been learned yet. Therefore, please learn the original ARP table before learning the current.".format(
                self.device.hostname))
            return None

    def __find_delta(self) -> tuple:

        delta_arp = 0
        percentage_delta_arp = 0

        if self.arp_entries_original != 0:
            delta_arp = self.arp_entries_original - self.arp_entries_current
            percentage_delta_arp = (
                delta_arp / self.arp_entries_original) * 100

        return (delta_arp, percentage_delta_arp)

    def is_changed(self):
        if hasattr(self, "delta_arp") and hasattr(self, "percentage_delta_arp"):
            if self.percentage_delta_arp > lost_arp_safe:
                return True
            else:
                return False
        else:
            return False

    def diff(self):
        if hasattr(self, "delta_arp") and hasattr(self, "percentage_delta_arp"):

            string = "There are {} ({:.2f}%) ARP entries is lost.".format(
                self.delta_arp, self.percentage_delta_arp
            )
            string = string + "\n"
            return string
        else:
            return None


@decorator_instance
class RoutingMonitor:

    def __init__(self, device):

        self.device = device

    def learn_routing(self) -> int:

        num_routes = 0
        try:
            Routing = get_ops('routing', self.device)
            routing_object = Routing(device=self.device)
            routing_object.learn()

            for vrf_key in routing_object.info["vrf"]:
                for ip_protocol_key in routing_object.info["vrf"][vrf_key]["address_family"]:
                    num_routes = num_routes + len(
                        routing_object.info["vrf"][vrf_key]["address_family"][ip_protocol_key][
                            "routes"
                        ]
                    )
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except ConnectionError:
            raise ConnectionError
        except:
            unsupport_list.append("RoutingMonitor_instance")
            print("Cannot monitor routing table.")
        return num_routes

    def original(self):

        if not have_original_dir:

            self.num_routes_original = self.learn_routing()
            routing_dict = dict()
            routing_dict["num_routes_original"] = self.num_routes_original
            with open("{}/routing.json".format(dir_original_snapshot_create), 'w') as f:
                f.write(json.dumps(routing_dict, indent=4))

        else:
            try:
                if os.path.isfile("{}/routing.json".format(dir_original_snapshot_import)):
                    with open("{}/routing.json".format(dir_original_snapshot_import), 'r') as f:
                        routing_dict = json.load(f)
                        self.num_routes_original = routing_dict["num_routes_original"]
                else:
                    unsupport_list.append("RoutingMonitor_instance")
            except:
                unsupport_list.append("RoutingMonitor_instance")

    def current(self):
        if hasattr(self, "num_routes_original"):
            self.num_routes_current = self.learn_routing()
            self.delta_routes, self.percentage_delta_routes = self.__find_delta()
            return None
        else:
            print("The original Routing table of {} have not been learned yet. Therefore, please learn the original Routing table before learning the current.".format(
                self.device.hostname))
            return None

    def __find_delta(self) -> tuple:

        delta_routes = 0
        percentage_delta_routes = 0

        if self.num_routes_original != 0:
            delta_routes = self.num_routes_original - self.num_routes_current
            percentage_delta_routes = (
                delta_routes / self.num_routes_original) * 100

        return (delta_routes, percentage_delta_routes)

    def is_changed(self):
        if hasattr(self, "delta_routes") and hasattr(self, "percentage_delta_routes"):
            if self.percentage_delta_routes > lost_routes_safe:
                return True
            else:
                return False
        else:
            return False

    def diff(self):
        if hasattr(self, "delta_routes") and hasattr(self, "percentage_delta_routes"):

            string = "There are {} ({:.2f}%) routes is lost.".format(
                self.delta_routes, self.percentage_delta_routes
            )
            string = string + "\n"
            return string
        else:
            return None


@decorator_instance
class OspfMonitor:

    def __init__(self, device):

        self.device = device

    def learn_ospf(self) -> list:

        ospf_neighbor_list = []
        try:
            Ospf = get_ops('ospf', self.device)
            ospf_object = Ospf(device=self.device)
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
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except ConnectionError:
            raise ConnectionError
        except:
            unsupport_list.append("OspfMonitor_instance")
            print("Cannot monitor OSPF neighbors")
        return ospf_neighbor_list

    def original(self):

        if not have_original_dir:
            self.ospf_neighbor_list_original = self.learn_ospf()
            with open("{}/ospf_neighbors_list.json".format(dir_original_snapshot_create), 'w') as f:
                f.write(json.dumps(self.ospf_neighbor_list_original, indent=4))

        else:
            try:
                if os.path.isfile("{}/ospf_neighbors_list.json".format(dir_original_snapshot_import)):
                    with open("{}/ospf_neighbors_list.json".format(dir_original_snapshot_import), 'r') as f:
                        self.ospf_neighbor_list_original = json.load(f)
                else:
                    unsupport_list.append("OspfMonitor_instance")
            except:
                unsupport_list.append("OspfMonitor_instance")

    def current(self):

        if hasattr(self, "ospf_neighbor_list_original"):

            self.ospf_neighbor_list_current = self.learn_ospf()
            self.neighbor_change_list, self.delta_ospf, self.percentage_delta_ospf = self.__find_ospf_neighbors_change()
            return None
        else:
            print("The original OSPF of {} have not been learned yet. Therefore, please learn the original OSPF before learning the current.".format(
                self.device.hostname))
            return None

    def __find_ospf_neighbors_change(self) -> tuple:

        neighbor_change_list = []
        for neighbor_original in self.ospf_neighbor_list_original:
            if neighbor_original["state"] != "full":
                continue
            else:
                count = 0
                for neighbor_current in self.ospf_neighbor_list_current:
                    if (
                        neighbor_current["vrf"] == neighbor_original["vrf"]
                        and neighbor_current["ospf_instance"]
                        == neighbor_original["ospf_instance"]
                        and neighbor_current["area"] == neighbor_original["area"]
                        and neighbor_current["neighbor_router_id"]
                        == neighbor_original["neighbor_router_id"]
                    ):

                        if (
                            neighbor_current.get("virtual_link", None)
                            and neighbor_current["virtual_link"]
                            == neighbor_original["virtual_link"]
                        ):
                            if neighbor_current["state"] != "full":
                                neighbor_change_list.append(neighbor_current)
                            break

                        elif (
                            neighbor_current.get("sham_link", None)
                            and neighbor_current["sham_link"]
                            == neighbor_original["sham_link"]
                        ):
                            if neighbor_current["state"] != "full":
                                neighbor_change_list.append(neighbor_current)
                            break

                        elif (
                            neighbor_current.get("interface", None)
                            and neighbor_current["interface"]
                            == neighbor_original["interface"]
                        ):
                            if neighbor_current["state"] != "full":
                                neighbor_change_list.append(neighbor_current)
                            break

                        count = 0
                        continue
                    else:
                        count = count + 1

                if count == len(self.ospf_neighbor_list_current):
                    neighbor_lost = {}
                    for key, value in neighbor_original.items():
                        if key == "state":
                            neighbor_lost["state"] = "Not found in OSPF neighbor table"
                        else:
                            neighbor_lost[key] = value
                    neighbor_change_list.append(neighbor_lost)

        delta_ospf = len(neighbor_change_list)
        percentage_delta_ospf = (
            len(neighbor_change_list) / len(self.ospf_neighbor_list_original)
        ) * 100

        return (neighbor_change_list, delta_ospf, percentage_delta_ospf)

    def is_changed(self):
        if hasattr(self, "neighbor_change_list"):
            if len(self.neighbor_change_list) > 0:
                return True
            else:
                return False
        else:
            return False

    def diff(self):
        if hasattr(self, "neighbor_change_list") and hasattr(self, "delta_ospf") and hasattr(self, "percentage_delta_ospf"):
            string = "\nThere are {} OSPF neighbors' state have been changed.\nList of the OSPF neighbors' state have been changed:\n".format(
                self.delta_ospf)
            if len(self.neighbor_change_list) > 0:
                for neighbor_dict in self.neighbor_change_list:

                    for key, value in neighbor_dict.items():
                        string = string + "   {}: {}\n".format(key, value)
                    string = string + "\n"
                return string
            else:
                string = string + "   None\n"
                return string
        else:
            return None


class AllDetail:
    def __init__(self, device):

        self.device = device

    def parse_all_cmd(self):

        cmd_list = []
        cmd_error_list = []

        output = self.device.parse("all")

        for cmd in output:
            if "errored" in output[cmd].keys():
                cmd_error_list.append(cmd)
        for cmd_error in cmd_error_list:
            del output[cmd_error]

        cmd_list = list(output.keys())

        for i in range(len(cmd_list)):
            if i == 0:
                exclude = get_parser_exclude(cmd_list[i], self.device)
            else:
                exclude.extend(get_parser_exclude(cmd_list[i], self.device))

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

        return output, exclude

    def original(self):

        if not have_original_dir:

            self.all_detail_original, self.exclude = self.parse_all_cmd()
            with open("{}/all_detail_original.json".format(dir_original_snapshot_create), 'w') as f:
                f.write(json.dumps(self.all_detail_original, indent=4))

        else:
            try:
                if os.path.isfile("{}/interface_up_list.json".format(dir_original_snapshot_import)):
                    with open("{}/all_detail_original.json".format(dir_original_snapshot_import), 'r') as f:
                        self.all_detail_original = json.load(f)
                else:
                    self.all_detail_original, self.exclude = self.parse_all_cmd()
            except:
                self.all_detail_original, self.exclude = self.parse_all_cmd()

    def current(self):
        self.all_detail_current, self.exclude = self.parse_all_cmd()

        if have_original_dir:
            all_detail_current_json = json.dumps(
                self.all_detail_current, indent=4)
            self.all_detail_current = json.loads(all_detail_current_json)

        self.diff_all_details = self.__find_diff_all_detail()

    def __find_diff_all_detail(self):
        diff = Diff(self.all_detail_original,
                    self.all_detail_current, exclude=self.exclude)
        diff.findDiff()
        return diff

    def is_changed(self):
        if hasattr(self, "diff"):
            if not (str(self.diff) == ""):
                return True
            else:
                return False
        else:
            return False

    def diff(self):
        if hasattr(self, "diff_all_details"):
            string = "\n{} {} {}\n".format("-"*40,
                                           datetime.now().strftime("%Y-%b-%d %X"), "-"*40)
            if not (str(self.diff_all_details) == ""):
                string = string + "   {}\n".format(self.diff_all_details)
            else:
                string = string + "None\n"

            string = string + "\n{}".format("-"*102)
            return string
        else:
            return None


def get_testbed() -> tuple:

    print()

    try:

        dir_running_script = os.path.dirname(os.path.realpath(__file__))

        if os.path.exists("{}/databaseconfig.py".format(dir_running_script)):
            print("Found {}/databaseconfig.py".format(os.path.abspath(os.getcwd())))

        import databaseconfig as cfg

        print("Imported databaseconfig.py file successfully.")

        input_dict = cfg.input_dict

        testbed_dict = {
            "devices": {
                input_dict["hostname"]: {
                    "alias": "uut",
                    "type": "Nexus",
                    "os": "nxos",
                    "connections": {"defaults": {
                        "class": "unicon.Unicon"},
                        "vty": {
                        "protocol": "ssh",
                        "ip": input_dict["ip"]}},
                    "credentials": {
                        "default": {
                            "password": input_dict["password"],
                            "username": input_dict["username"]}
                    }
                }
            }
        }

        lost_mac_safe = cfg.lost_mac_safe
        lost_arp_safe = cfg.lost_arp_safe
        lost_routes_safe = cfg.lost_routes_safe
        dir_output = cfg.dir_output
        while not os.path.exists("{}".format(dir_output)):
            print("{} directory does not exist.".format(dir_output))
            dir_output = input(
                "Enter the directory that will store the output files (e.g. /home/script): ")

        global have_original_dir
        global dir_original_snapshot_import
        try:
            dir_original_snapshot_import = cfg.dir_original_snapshot
            if not os.path.exists("{}".format(dir_original_snapshot_import)):
                print("\n{} directory does not exist.".format(dir_output))
                have_snapshot = input(
                    "Do you have the original snapshot directory (Y or N): ")

                while have_snapshot.upper() != "Y" and have_snapshot.upper() != "N":
                    print("Your input is invalid. Please enter Y or N.")
                    have_snapshot = input(
                        "Do you have the original snapshot directory (Y or N): ")
                if exit.upper() == "Y":
                    dir_original_snapshot_import = input(
                        "Enter the directory original snapshot directory (e.g. /home/script): ")
                    while not os.path.exists("{}".format(dir_original_snapshot_import)):
                        print("{} directory does not exist.".format(
                            dir_original_snapshot_import))
                        dir_original_snapshot_import = input(
                            "Enter the directory original snapshot directory (e.g. /home/script): ")

                    have_original_dir = True
                else:
                    print("The program will learn the original snapshot.\n")
                    have_original_dir = False
            else:
                have_original_dir = True
        except AttributeError:
            print("\nThe program did not find the orginal snapshot directory in databaseconfig.py.\nThe program will learn the original snapshot and save it in {}.".format(dir_output))
            have_original_dir = False
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
        while True:
            lost_mac_safe = input(
                "Enter the percentage lost of insignificant amount of MAC addresses: "
            )
            try:
                lost_mac_safe = int(lost_mac_safe)
                break
            except ValueError:
                try:
                    lost_mac_safe = float(lost_mac_safe)
                    break
                except ValueError:
                    print("You have entered invalid value. Please enter a number.")

        while True:
            lost_arp_safe = input(
                "Enter the percentage lost of insignificant amount of ARP entries: "
            )
            try:
                lost_arp_safe = int(lost_arp_safe)
                break
            except ValueError:
                try:
                    lost_arp_safe = float(lost_arp_safe)
                    break
                except ValueError:
                    print("You have entered invalid value. Please enter a number.")

        while True:
            lost_routes_safe = input(
                "Enter the percentage lost of insignificant amount of routes in routing table: "
            )
            try:
                lost_routes_safe = int(lost_routes_safe)
                break
            except ValueError:
                try:
                    lost_routes_safe = float(lost_routes_safe)
                    break
                except ValueError:
                    print("You have entered invalid value. Please enter a number.")

        testbed_dict = {
            "devices": {
                hostname: {
                    "alias": "uut",
                    "type": "Nexus",
                    "os": "nxos",
                    "connections": {"defaults": {
                        "class": "unicon.Unicon"},
                        "vty": {
                        "protocol": "ssh",
                        "ip": ip}},
                    "credentials": {
                        "default": {
                            "password": password,
                            "username": username}
                    }
                }
            }
        }

        have_snapshot = input(
            "Do you have the original snapshot directory (Y or N): ")

        while have_snapshot.upper() != "Y" and have_snapshot.upper() != "N":
            print("Your input is invalid. Please enter Y or N.")
            have_snapshot = input(
                "Do you have the original snapshot directory (Y or N): ")
        if exit.upper() == "Y":
            dir_original_snapshot_import = input(
                "Enter the directory original snapshot directory (e.g. /home/script): ")
            while not os.path.exists("{}".format(dir_original_snapshot_import)):
                print("{} directory does not exist.".format(
                    dir_original_snapshot_import))
                dir_original_snapshot_import = input(
                    "Enter the directory original snapshot directory (e.g. /home/script): ")
            have_original_dir = True
        else:
            print("The program will learn the original snapshot.\n")
            have_original_dir = False

        dir_output = input(
            "Enter the directory that will store the output files (e.g. /home/script): ")

        while not os.path.exists("{}".format(dir_output)):
            print("{} directory does not exist.".format(dir_output))
            dir_output = input(
                "Enter the directory that will store the output files (e.g. /home/script): ")

    if len(dir_output) > 1 and dir_output[-1] == "/":
        dir_output = dir_output[:-1]
    lost_safe_tuple = (lost_mac_safe, lost_arp_safe, lost_routes_safe)

    return (testbed_dict, lost_safe_tuple, dir_output)


def runThreadPoolExecutor(instance_monitor_dict, method_name):

    executor_dict = dict()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for instance_name, instance in instance_monitor_dict.items():
            if hasattr(instance, method_name):
                if (callable(getattr(instance, method_name))):
                    method = getattr(instance, method_name)
                    executor_dict[instance_name +
                                  "executor"] = executor.submit(method)


def prepend_line(file_name, line):
    """Insert given string as a new line at the beginning of a file"""

    if not os.path.exists("{}".format(file_name)):
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

    testbed_dict, lost_safe_tuple, dir_output = get_testbed()

    device = Device(testbed_dict)

    global lost_mac_safe, lost_arp_safe, lost_routes_safe, dir_original_snapshot_create
    lost_mac_safe, lost_arp_safe, lost_routes_safe = lost_safe_tuple

    try:
        if not device.device.is_connected():
            device.make_connection()
    except ConnectionError:
        print("\nERROR: Can't establish the connection to the {}.".format(
            device.device.hostname))
        print("Please check the hostname, IP aaddress, username, and password.\n")
        sys.exit()

    if device.device.is_connected():
        print("{} is connected.".format(device.device.hostname))
    else:
        print("{} is not connected.".format(device.device.hostname))

    if os.path.isfile("{}/all_diff_output.txt".format(dir_output)):
        os.remove("{}/all_diff_output.txt".format(dir_output))

    if os.path.isfile("{}/common_diff_output.txt".format(dir_output)):
        os.remove("{}/common_diff_output.txt".format(dir_output))

    # print(class_list)
    instance_monitor_dict = dict()
    for class_element in class_list:
        instance = class_element(device.device)
        key = "{}_instance".format(type(instance).__name__)
        instance_monitor_dict[key] = instance
        # print(instance)

    # print(list(instance_monitor_dict.keys()))

    have_original = False
    is_detail = False

    try:
        if not have_original:
            print("The program is learning {}'s common information for the original state...".format(
                device.device.hostname))
            now1 = datetime.now()
            # runThreadPoolExecutor(instance_monitor_dict, "original")

            if not have_original_dir:
                while True:
                    dir_original_snapshot_create = "{}/{}_original_snapshot_{}".format(device.device.hostname,
                                                                                       dir_output, datetime.now().strftime("%Y%m%d-%H%M%S"))
                    if not os.path.exists(dir_original_snapshot_create):
                        os.makedirs(dir_original_snapshot_create)
                        break

            for instance in instance_monitor_dict.values():
                instance.original()
            now2 = datetime.now()

            print(
                "The common information for original state has learned in {:.2f} seconds.".format(
                    (now2 - now1).total_seconds()
                )
            )

            # print(unsupport_list)
            for unsupport in unsupport_list:
                instance_monitor_dict.pop(unsupport, None)

            print("The program is learning {}'s all details for the original state...".format(
                device.device.hostname))
            now1 = datetime.now()
            alldetail_instance = AllDetail(device.device)
            alldetail_instance.original()
            now2 = datetime.now()
            print(
                "The all details for original state has learned in {:.2f} seconds.".format(
                    (now2 - now1).total_seconds()
                )
            )

            have_original = True

    except KeyboardInterrupt:
        print("\nThe program has exited before learning's original state.\n".format(
            device.device.hostname))
        sys.exit()

    except ConnectionError:
        print(
            "\nThe connection to {} has been disconnected before learning original state.\n".format(
                device.device.hostname)
        )
        sys.exit()

    lost_mac_safe, lost_arp_safe, lost_routes_safe = lost_safe_tuple
    print("The programs is beginning to monitor {}...".format(
        device.device.hostname))
    while True:
        try:
            if not device.device.is_connected():
                device.make_connection()

            # runThreadPoolExecutor(instance_monitor_dict, "current")
            for instance in instance_monitor_dict.values():
                instance.current()

            # print(unsupport_list)
            for unsupport in unsupport_list:
                instance_monitor_dict.pop(unsupport, None)

            if not instance_monitor_dict:
                print("\nThe {} device does not support any monitoring category in this tool.\n".format(
                    device.device.hostname))
                sys.exit()

            string = ""
            string = string + "\n{} {} {}\n".format("-"*40,
                                                    datetime.now().strftime("%Y-%b-%d %X"), "-"*40)

            is_changed = False
            for key, value in instance_monitor_dict.items():
                if value.is_changed():
                    is_changed = True
                    break

            if is_changed:
                for key, value in instance_monitor_dict.items():
                    string = string + value.diff()
            else:
                string = string + "{} does not change.\n".format(
                    device.device.hostname)
            string = string + "\n{}".format("-"*102)

            print(string)
            prepend_line(
                "{}/common_diff_output.txt".format(dir_output), string)

            if is_detail:
                print("\nThe program is parsing all commands...")
                alldetail_instance.current()
                string = alldetail_instance.diff()
                print(
                    "The program has finished parsing all commands.\nPlease check the differences in {}/all_diff_output.txt file.".format(
                        dir_output)
                )
                print("{}\n".format("-"*102))
                prepend_line(
                    "{}/all_diff_output.txt".format(dir_output), string)

        except KeyboardInterrupt:
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
            device.device.disconnect_all()

        except ConnectionError:
            print("\nThe connection is disconnected. The device may be reloading.")
            print("The program will try to re-connect after 30 seconds.\n")
            sleep(30)


if __name__ == '__main__':
    try:

        # Uncomment six lines below to import and decorate classes from extra.py
        # import inspect
        # import extra
        # extra_class_list = [m[1] for m in inspect.getmembers(
        #     extra, inspect.isclass) if m[1].__module__ == extra.__name__]
        # for extraClass in extra_class_list:
        #     extraClass = decorator_instance(extraClass)

        main()
    except SystemExit:
        sys.exit()
    except:
        print("\nSomethings went wrong.")
        print("Unexpected error:", sys.exc_info()[0])
        sys.exit()
