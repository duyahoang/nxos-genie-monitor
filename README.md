
<!-- PROJECT LOGO -->
<br />
<p align="center">

  <h1 align="center">NXOS-Genie-Monitor</h1>

<!-- TABLE OF CONTENTS -->
<details open="open">
  <summary><h2 style="display: inline-block">Table of Contents</h2></summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

The tool utilizes the PyATS/Genie from Cisco to take a snapshot of the original operational state of the Nexus device, including common information(interfaces, VLAN, MAC address, ARP, routing table, and OSPF neighbors) and parsing all show commands that the pyATS/Genie library supports. 
Then, the tool runs an infinity loop to capture the device's current state and compare it with the original state to find the differences.

The tool supports two modes. The first mode (default) only compares the common information, and the second mode compares all show commands in the current state and original state.
Using Ctrl-C to pause the program to change the mode or exit the program.

The tool prints the difference in the common information and also stores it in common_diff_output.txt. The difference of all details shows common is stored in all_diff_output.txt.



<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple steps.

### Prerequisites

This is an example of how to list things you need to use the software and how to install them.
* Python 3.6 and above
* pip
  ```sh
  pip install pyats[library]
  ```

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/duyahoang/nxos-genie-monitor.git
   ```
2. Install PyATS/Genie packages
   ```sh
   pip install pyats[library]
   ```



<!-- USAGE EXAMPLES -->
## Usage

* Edit the databaseconfig.py file to add device's information such as hostname, IP address, username, password, and the directory that will store the output files.
* Run the nxos_monitor_oop.py script. The script will take the input from the databaseconfig.py file. If the file does not exist, the tool will ask for the input.
* Now, the tool will capture the original state of the device and monitor after that.
* Using Ctrl-C to pause the program to change the mode(only common or all details) or exit the program.
* The tool can be easily extended the capability. The developer only need to create a new class with constructor, original, current, is_changed, and diff methods to add a new common information.





<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.



<!-- CONTACT -->
## Contact

Duy Hoang - duyhoan@cisco.com

Project Link: [https://github.com/duyahoang/nxos-genie-monitor](https://github.com/duyahoang/nxos-genie-monitor)

