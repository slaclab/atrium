import settings

import numpy as np
import os
import re
import random
import subprocess
from epics import caget, caput, camonitor, camonitor_clear, PV

class BLD_TESTER:
    def __init__(self):
        print("Initializing BLD_TESTER\n")
        self.prefix = settings.cmd_env_paths["P"]
        self.logger = settings.logger

        self.bld_decode_path = ""
        self.replace_path_env(settings.bld_decode_path)

        self.bld_global_pv_control = ""
        self.bld_multicast_ip = ""
        self.bld_multicast_port = ""
        self.bld_fixed_rate = ""
        self.bld_acquisition = ""

        # key: type of data, val: data
        self.packet1 = {}
        self.packet2 = {}

    def test_bld_configurations(self):
        print("Checking BLD configurations")
        for frequency in settings.bld_config_list:

            print("\n------------------------")
            print("Testing Frequency " + str(frequency))
            print("------------------------")

            # Test number of channels
            self.test_num_channels(frequency)

            # Test for all fixed rates
            for rate_name, rate_val in settings.bld_fixed_rates.items():
                print("\n!!!!!!!-- RATE " + rate_name + " --!!!!!!!\n")

                packets = self.get_packet_pair(frequency, rate_name)

                # Check if the channel names are correct
                self.check_packets_channels()

                # Test the channel from bldDecode is equal to channels in st.cmd
                print("PID Packet 1     --> ", self.format_array(self.packet1["pid_list"], threshold = 10))
                self.check_packet_PID_update_rate(frequency, rate_name, rate_val, packet_num = 1)
                print("Delta Packet 1   --> ", self.format_array(self.packet1["delta_list"], threshold = 10))
                self.check_packet_delta_update_rate(frequency, rate_name, rate_val, packet_num = 1)
                print("PID Packet 2     --> ", self.format_array(self.packet2["pid_list"], threshold = 10))
                self.check_packet_PID_update_rate(frequency, rate_name, rate_val, packet_num = 2)
                print("Delta Packet 2   --> ", self.format_array(self.packet2["delta_list"], threshold = 10))
                self.check_packet_delta_update_rate(frequency, rate_name, rate_val, packet_num = 2)
                self.check_PID_diff_between_packet(frequency, rate_val)
                
                for channel in self.packet1["channel_info"].keys():
                    print("\n*****<< " + " Channel " + channel + " >>*****\n")
                    channel_vals1 = self.packet1["channel_info"][channel]
                    channel_vals2 = self.packet2["channel_info"][channel]

                    print("Packet 1     --> ", self.format_array(channel_vals1, threshold = 10))
                    print("Packet 2     --> ", self.format_array(channel_vals2, threshold = 10))
                    
                    # Test if there are NaN in the channel data
                    self.check_nan_in_channel_data(channel)

                    # Test data for each channel changes over time for packet one
                    self.check_channel_data_change_in_time(channel)

                    # Test data changes between packets 
                    self.check_pair_for_diff_channel_data(channel)                    

                self.reset_config()

    def enable_all_channels(self):
        for ch in settings.bld_channels:
            caput(self.prefix + ":" + ch + "BLDCHNMASK", 1, wait=True)

    def get_packet_pair(self, freq, rate):
        self.config_freq(freq, rate)
        self.enable_all_channels()
        output = self.run_bld_decode(num_packets = 2)
        packets = self.extract_packets(output)

        # Store information from packet 1
        pid_list, delta_list, channel_data = self.parse_packet(packets[0])
        self.packet1["pid_list"] = pid_list
        self.packet1["delta_list"] = delta_list
        self.packet1["channel_info"] = channel_data

        # Store information from packet 2
        pid_list, delta_list, channel_data = self.parse_packet(packets[1])
        self.packet2["pid_list"] = pid_list
        self.packet2["delta_list"] = delta_list
        self.packet2["channel_info"] = channel_data

    def config_freq(self, frequency, rate):
        self.bld_global_pv_control = self.prefix + ":BLD_LOCAL"
        self.bld_multicast_ip = self.prefix + ":BLD" + str(frequency) + "_MULT_ADDR"
        self.bld_multicast_port = self.prefix + ":BLD" + str(frequency) + "_MULT_PORT"
        self.bld_fixed_rate = self.prefix + ":BLD" + str(frequency) + "_FIXEDRATE"
        self.bld_acquisition = self.prefix + ":BLD" + str(frequency) + "_ACQ"

        # TODO: Use random multicast IP and port instead of fixed
        caput(self.bld_global_pv_control, 0)
        caput(self.bld_multicast_ip, "134.79.216.240")
        caput(self.bld_multicast_port, 10148)
        caput(self.bld_fixed_rate, rate)
        caput(self.bld_acquisition, 1)

    def reset_config(self):
        caput(self.bld_global_pv_control,1)
        caput(self.bld_multicast_ip,'')
        caput(self.bld_multicast_port,0)
        caput(self.bld_fixed_rate, "1Hz")
        caput(self.bld_acquisition, 0)

    def run_bld_decode(self, num_packets):
        output_info = subprocess.run(["./bldDecode", "-b", "EM2K0:XGMD:HPS:BLD_PAYLOAD", "-p", "10148", "-n", str(num_packets), "-d"], capture_output=True, cwd = self.bld_decode_path)
        output_bytestr = output_info.stdout
        output = output_bytestr.decode('utf-8')
        return output

    # TODO: Works with default path but needs to be tested more (especially if user inputs relative/absolute path)
    def replace_path_env(self, bld_decode_path):
        #replace env variables in bldDecode path

        bld_decode_path += '/bin/rhel7-x86_64'
        # Split by path seperators
        bld_decode_split = bld_decode_path.split(os.sep)
        # For each part of path, replace env var with actual val
        for i, part in enumerate(bld_decode_split):
            if '$' in part:
                env_val = os.getenv(part[1:]) # Remove $ character of env variable
                bld_decode_split[i] = env_val
        self.bld_decode_path = os.path.join("/",*bld_decode_split) # Make it an absolute path

    def extract_packets(self, output):
        # Regex matches with non-greedy info starting with "new packet size" and "ending with packet finished" lines
        packets_pattern = r"====== new packet size \d+ ======(.*?)====== Packet finished ======"
        packets = re.findall(packets_pattern, output, re.DOTALL)

        return packets

    def parse_packet(self, packet):
        # Regex matches events
        event_pattern = r"===> event \d+"
        # Regex matches for pid
        pid_pattern = r"(?:Pulse ID|pulseID)\s*: (0x[0-9A-Fa-f]+)"
        # Regex matches for delta with PID before, captures only delta
        delta_pattern = r"Pulse ID\s*: 0x[0-9A-Fa-f]+ delta (0x[0-9A-Fa-f]+)"
        # Regex matches "[channel name] raw=0x(hex chars), float = (decimal val)"; Captures channel, raw val, float val
        channel_pattern = r"(\w+) raw=0x[0-9A-Fa-f]+, float=([-\d.]+)"
        
        pid_list = []
        delta_list = []
        channel_data = {} # Key: channel name; value: data for channel

        events = re.split(event_pattern, packet)
        for event in events:
            pid_match = re.search(pid_pattern, event)
            pid = pid_match.group(1)
            pid_list.append(int(pid,0))

            delta_match = re.search(delta_pattern, event)
            if delta_match:
                delta = delta_match.group(1)
                delta_list.append(int(delta,0))

            channels = re.findall(channel_pattern, event)
            for data in channels:
                channel_name = data[0]
                float_val = data[1]

                if channel_name not in channel_data:
                    channel_data[channel_name] = []
                channel_data[channel_name].append(float(float_val))
        
        return pid_list, delta_list, channel_data

    def test_num_channels(self, freq):
        # Randomly enable/disable channels and test if channels change accordingly
        print("\nEnable/Disable Random Channels Test")
        # Repeat test 3 times
        for test_num in range(3):
            # Choose a few random channels
            num_channels = random.randint(1, len(settings.bld_channels))
            random_channels = random.sample(settings.bld_channels, k = num_channels)

            # Enable chosen channels and disable others
            for ch in settings.bld_channels:
                if ch in random_channels:
                    caput(self.prefix + ":" + ch + "BLDCHNMASK", 1, wait=True) # enable channel
                else:
                    caput(self.prefix + ":" + ch + "BLDCHNMASK", 0, wait=True) # disable channel

            # Get channel list of data 
            self.config_freq(freq, rate = "10kHz")
            packet = self.run_bld_decode(num_packets = 1)
            pid_list, delta_list, channel_data = self.parse_packet(packet)
            channel_list = channel_data.keys()

            if set(random_channels) == set(channel_list):
                print("Test " + str(test_num + 1) + ":         OK")
            else:
                self.logger.error("[ERROR] -    " + "List of enabled channels does not match decoded channels")
                self.logger.error("             " + "Enabled channels: " + str(list(random_channels)))
                self.logger.error("             " + "Decoded channels: " + str(list(channel_list)))

    def check_packets_channels(self):
        if set(settings.bld_channels) != set(self.packet1["channel_info"].keys()) or set(settings.bld_channels) != set(self.packet2["channel_info"].keys()):
            self.logger.error("[ERROR] -    " + "Incorrect channels in packets.")
            self.logger.error("             " + "Enabled channels: " + str(settings.bld_channels))
            self.logger.error("             " + "Decoded channels: " + str(list(self.packet1["channel_info"].keys())))
        else:
            print("Correct Channels:            OK")
    
    def check_channel_data_change_in_time(self, channel):
        channel_vals1 = self.packet1["channel_info"][channel]
        channel_vals2 = self.packet2["channel_info"][channel]
        # Check to see if we always get the same value for a channel
        if (np.array(channel_vals1) == np.array(channel_vals1)[-1]).all() or (np.array(channel_vals2) == np.array(channel_vals2)[-1]).all():
            self.logger.warning("[WARNING]  - Channel " + channel + " keeps the same value over time.")
            self.logger.warning("             Is IOC triggering the firmware correctly?")
        else:
            print("Updated With New Data:       OK")

    def check_pair_for_diff_channel_data(self, channel):
        channel_vals1 = self.packet1["channel_info"][channel]
        channel_vals2 = self.packet2["channel_info"][channel]

        if np.array_equal(np.array(channel_vals1), np.array(channel_vals2)) and np.array(channel_vals1).size != 0:
            self.logger.critical("[CRITICAL] - " + "Channel " + channel + " is not updated with new values.")
            self.logger.critical("             Sampling too fast or is the channel value constant?")
        else:
            print("Pair Of Channel Data Diff:   OK")

    def check_packet_PID_update_rate(self, freq, rate_name, rate, packet_num):
        update_rate = self.compute_PID_or_delta_update_rate(packet_num, isPID = True)
        self.compare_PID_update_rate(freq, rate_name, rate, update_rate)

    def check_packet_delta_update_rate(self, freq, rate_name, rate, packet_num):
        delta_update_rate = self.compute_PID_or_delta_update_rate(packet_num, isPID = False)
        self.compare_delta_update_rate(freq, rate_name, rate, delta_update_rate)

    #TODO: Change variable names
    def compute_PID_or_delta_update_rate(self, packet_num, isPID):
        if packet_num == 1 and isPID:
            signal_data = self.packet1["pid_list"]
        elif packet_num == 2 and isPID:
            signal_data = self.packet2["pid_list"]
        elif packet_num == 1 and not isPID:
            signal_data = self.packet1["delta_list"]
        else:
            signal_data = self.packet2["delta_list"]

        if len(signal_data) < 2:
            return -2
        PID_data = list(reversed(signal_data))
        prev_diff = PID_data[0] - PID_data[1]
        for i in range(2, len(PID_data)):
            prev_PID = PID_data[i-1]
            cur_PID = PID_data[i]
            diff = prev_PID - cur_PID
            if np.not_equal(diff, prev_diff):
                print("diff", diff)
                #PID update rate is inconsistent
                return -1
        return prev_diff

    def compare_delta_update_rate(self, freq, rate_name, update_rate, diff):
        delta_update_rate = update_rate
        measured_delta_update_rate = settings.core_linac_freq / diff
        if diff == -1:
            self.logger.error("[ERROR] -    Delta diffs are not consistent between elements for Frequency " + str(freq) + " at " + rate_name)
            self.logger.error("             Please make sure that sampling of data is done at consistent intervals.")
            self.logger.error("             Ignore this error if firmware/IOC has just been rebooted.")
        elif diff == -2:
            self.logger.error("[ERROR] -    Frequency " + str(freq) + " at " + rate_name + " delta array is empty or only contains one element.")
        elif not np.equal(measured_delta_update_rate, delta_update_rate):
            self.logger.error("[ERROR] -    Frequency " + str(freq) + " at " + rate_name + " the delta update rate (" + str(measured_delta_update_rate) + \
            "Hz) doesn't match the delta update rate of " + str(delta_update_rate) + "Hz")
            self.logger.error("             Please make sure that sampling of data is done at consistent intervals.")
        else:
            print("Delta Update Rate:             OK (" + str(measured_delta_update_rate) + "Hz)")

    def compare_PID_update_rate(self, freq, rate_name, update_rate, diff):
        # We have a user buffer, extract update rate from buffer rate dictionary  
        pid_update_rate = update_rate
        pv_update_rate = settings.core_linac_freq / diff
        if diff == -1:
            self.logger.error("[ERROR] -    PID diffs are not consistent between elements for Frequency " + str(freq) + " at " + rate_name)
            self.logger.error("             Please make sure that sampling of data is done at consistent intervals.")
            self.logger.error("             Ignore this error if firmware/IOC has just been rebooted.")
        elif diff == -2:
            self.logger.error("[ERROR] -    Frequency " + str(freq) + " at " + rate_name + " PID array is empty or contains only one element")
        elif not np.equal(pid_update_rate, pv_update_rate):
            self.logger.error("[ERROR] -    Frequency " + str(freq) + " at " + rate_name + " the PID update rate (" + str(pid_update_rate) + \
            "Hz) doesn't match the PV update rate of " + str(pv_update_rate) + "Hz")
            self.logger.error("             Please make sure that sampling of data is done at consistent intervals.")
        else:
            print("PID Update Rate:             OK (" + str(pid_update_rate) + "Hz)")

    def format_array(self, array, threshold):
        # returns string of array to print
        leading_elements = preceding_elements = 3
        if len(array) > threshold:
            head_str = ', '.join(map(str, array[:leading_elements]))
            tail_str = ', '.join(map(str, array[-preceding_elements:]))
            return "[" + head_str + " ... " + tail_str + "] (" + str(len(array)) + ")"
        else:
            return "[" + ', '.join(map(str, array)) + "] (" + str(len(array)) + ")"

    def check_nan_in_channel_data(self, channel):
        channel_data1 = self.packet1["channel_info"][channel]
        channel_data2 = self.packet2["channel_info"][channel]
        # Check for at least one NaN value
        if np.isnan(np.sum(channel_data1)) or np.isnan(np.sum(channel_data2)):
            self.logger.error("[ERROR]    - " + pv_name + " contains NaN values.")
        else:
            print("PV Does Not Have NaNs:       OK")
    
    def check_PID_diff_between_packet(self, freq, update_rate):
        init_PID1 = self.packet1["pid_list"][-1] # PID of last event
        init_PID2 = self.packet2["pid_list"][0]

        measured_rate = init_PID2 - init_PID1
        packet_update_rate = settings.core_linac_freq / measured_rate

        if packet_update_rate == update_rate:
            print("PID Diff Between Packets     OK")
        else:
            self.logger.error("[ERROR] -    PID diffs are not consistent between packets for frequency " + str(freq) + " at rate " + update_rate)
        