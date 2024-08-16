import settings

import os
import re
import subprocess
from epics import caget, caput, camonitor, camonitor_clear, PV

class BLD_TESTER:
    def __init__(self):
        print("Initializing BLD_TESTER\n")
        self.prefix = settings.cmd_env_paths["P"]

        self.bld_decode_path = ""
        self.replace_path_env(settings.bld_decode_path)

        self.bld_global_pv_control = ""
        self.bld_multicast_ip = ""
        self.bld_multicast_port = ""
        self.bld_fixed_rate = ""
        self.bld_acquisition = ""

    def test_bld_configurations(self):
        # for freq in settings.bld_config_list:
        self.config_freq(1)
        output = self.run_bld_decode()
        self.extract_packets(output)
        self.reset_config()

    def config_freq(self, frequency):
        self.bld_global_pv_control = self.prefix + ":BLD_LOCAL"
        self.bld_multicast_ip = self.prefix + ":BLD" + str(frequency) + "_MULT_ADDR"
        self.bld_multicast_port = self.prefix + ":BLD" + str(frequency) + "_MULT_PORT"
        self.bld_fixed_rate = self.prefix + ":BLD" + str(frequency) + "_FIXEDRATE"
        self.bld_acquisition = self.prefix + ":BLD" + str(frequency) + "_ACQ"

        caput(self.bld_global_pv_control, 0)
        caput(self.bld_multicast_ip, "134.79.216.240")
        caput(self.bld_multicast_port, 10148)
        caput(self.bld_fixed_rate, "10kHz")
        caput(self.bld_acquisition, 1)

    def reset_config(self):
        caput(self.bld_global_pv_control,1)
        caput(self.bld_multicast_ip,'')
        caput(self.bld_multicast_port,0)
        caput(self.bld_fixed_rate, "1Hz")
        caput(self.bld_acquisition, 0)

    def run_bld_decode(self):
        output_info = subprocess.run(["./bldDecode", "-b", "EM2K0:XGMD:HPS:BLD_PAYLOAD", "-p", "10148", "-n", "2", "-d"], capture_output=True, cwd = self.bld_decode_path)
        output_bytestr = output_info.stdout
        output = output_bytestr.decode('utf-8')
        return output

    def replace_path_env(self, bld_decode_path):
        #replace env variables in bldDecode path
        bld_decode_path += '/bin/rhel7-x86_64'
        bld_decode_split = bld_decode_path.split(os.sep)
        for i, part in enumerate(bld_decode_split):
            if '$' in part:
                env_val = os.getenv(part[1:]) # remove $ character of env variable
                bld_decode_split[i] = env_val
        self.bld_decode_path = os.path.join("/",*bld_decode_split) # absolute path

    def extract_packets(self, output):
        PID_list = []
        delta_list = []
        packets = output.split("====== Packet finished ======")
        for packet in packets:
            events = re.split(r"===> event \d+", packet)
            events = events[1:]
            for event in events:
                PID_match = re.search(r"Pulse ID\s+: [^\s]+", event)
                delta_match = re.search(r"delta [^\s]+", event)

                if PID_match:
                    PID_line = PID_match.group()
                    PID = PID_line.split(" : ")[1]
                    PID_list.append(PID)
                if delta_match:
                    delta_line = delta_match.group()
                    delta = delta_line.split()[1]
                    delta_list.append(delta)

                event_payload = event.split("Data payload:")[1]
                event_payload = event_payload.split('\n')
                for line in event_payload:
                    print("channel", line)