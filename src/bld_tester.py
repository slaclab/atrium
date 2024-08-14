import settings

import os
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
        for freq in settings.bld_config_list:
            self.config_freq(freq)
            output = self.run_bld_decode()
            self.extract_bld_decode_data(output)
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

    def run_bld_decode(self):
        output_info = subprocess.run(["./bldDecode", "-b", "EM2K0:XGMD:HPS:BLD_PAYLOAD", "-p", "10148", "-n", "1", "-d"], capture_output=True, cwd = self.bld_decode_path)
        output_bytestr = output_info.stdout
        output_string = output_bytestr.decode('utf-8')
        output = output_string.splitlines()
        return output

    def reset_config(self):
        caput(self.bld_global_pv_control,1)
        caput(self.bld_multicast_ip,'')
        caput(self.bld_multicast_port,0)
        caput(self.bld_fixed_rate, "1Hz")
        caput(self.bld_acquisition, 0)

    def replace_path_env(self, bld_decode_path):
        #replace env variables in bld decode path
        bld_decode_split = bld_decode_path.split(os.sep)
        for i, part in enumerate(bld_decode_split):
            if '$' in part:
                env_val = os.getenv(part[1:]) # remove $ character of env variable
                bld_decode_split[i] = env_val
        self.bld_decode_path = os.path.join('/', *bld_decode_split)

    def extract_bld_decode_data(self, output):
        for line in output:
            print(line)
