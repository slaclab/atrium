import time
import numpy as np
import settings

from dataclasses import dataclass
from typing import List
from epics import caget, caput, camonitor, camonitor_clear, PV

@dataclass
class PV_DATA:
    signal_data1 : List
    signal_data2 : List
    
class USR_BUFF_TESTER:
    """
    This class will test BSA/BSSS user buffers.
    """
    def __init__(self):
        print("Initializing USR_BUFF_TESTER\n")

        settings.bsa_usr_buff = True
        self.logger = settings.logger

        # Key: PV name; value: PV data
        self.user_buffer_pv_data = {}
        self.user_buffer_pid_pv_data = {}

        self.rate_num = 0   # the index of rate being acquired in usr_buff_fixed_rates
        self.sample_num = 1 # number of sample of PV that is being acquired (total of 2 samples per rate)
        
        self.sample_size = 0

#### CORE FUNCTIONS

    def test_bsss_user_buffers(self):
        print("Checking BSSS user buffers.")
        settings.bsss_usr_buff_acq = True
        list_of_signal_pvs = settings.service_pv_prefixes["BSSS"]

        self.core_test_user_buffers(list_of_signal_pvs, settings.bsss_scalar_type_suffixes, settings.bsss_usr_buff_idx_range, 
        settings.bsss_usr_buff_fixed_rates, samples = settings.bsss_num_samples)

    def test_bsa_user_buffers(self):
        print("Checking BSA user buffers.")
        settings.bsss_usr_buff_acq = False
        list_of_signal_pvs = settings.service_pv_prefixes["BSA"]

        self.core_test_user_buffers(list_of_signal_pvs, settings.bsa_hst_type_suffixes,
        settings.bsa_usr_buff_idx_range, settings.bsa_usr_buff_fixed_rates, samples=settings.bsa_usr_buff_elements)

    def core_test_user_buffers(self, signal_pvs, variable_type_suffixes, usr_buff_idx_range, usr_buff_fixed_rates, samples):
        for idx in usr_buff_idx_range:
            print("\n------------------------")
            print("Testing User Buffer " + str(idx))
            print("------------------------")

            # Get PVs that will be tested and another list including only PID PV's
            pvlist, pid_pvlist = self.get_pv_lists(idx, signal_pvs, variable_type_suffixes)

            for rate, rate_val  in usr_buff_fixed_rates.items():

                print("\n!!!!!!!-- RATE " + rate + " --!!!!!!!\n")

                # Acquire data of all pv's that will be used for testing
                self.get_pvs_data(idx, pvlist, pid_pvlist, samples, rate)

                # Run tests for all user buffers
                self.run_tests(samples, rate_val, pid_pvlist)

                # Resets user data and data for pv lists
                self.reset_data()

    def get_pvs_data(self, idx, pvlist, pid_pvlist, samples, rate):
        self.prep_user_buffer(idx, rate, samples=samples)
        self.get_pvs_data_pair(pvlist, rate)
        self.get_pvs_data_single(pid_pvlist, rate)

    def get_pv_lists(self, idx, signal_pvs, variable_type_suffixes):
        pvlist = []
        pid_pvlist = []

        for signal_pv in signal_pvs:
            for var_type in variable_type_suffixes:
                pv = signal_pv + var_type + str(idx)
                pvlist.append(pv)
                if "PID" in pv:
                    pid_pvlist.append(pv)

        return pvlist, pid_pvlist

    def run_tests(self, samples, rate, pid_pvlist):
        for pv_name, pv_data in self.user_buffer_pv_data.items(): 
            print("\n*****<< " + pv_name + " >>*****\n")
            print("First sample   --> " + self.format_array(pv_data.signal_data1, threshold = 15))
            print("Second sample  --> " + self.format_array(pv_data.signal_data2, threshold = 15))
            
            # Check if both samples are populated with data
            empty = self.check_pair_for_packed_pv_data(pv_name, pv_data)
            if empty:
                print("PV is empty")
                return

            # Check for NaN values
            self.check_pv_for_nan_data(pv_name, pv_data)

            # Check to see if we always get the same value in the latest sample 
            self.check_pv_for_updated_data(pv_name, pv_data)

            # Check if the bsa buffers changed in time.
            self.check_pair_for_diff_pv_data(pv_name, pv_data)
            
            print("\nTested with only 'First sample':")

            # Check if the number of elements are correct (only for BSA)
            self.check_number_of_elements_usr_buff(pv_name, samples)
            
            # Check if the PID changes as expected (for a PID-type PV only)
            if pv_name in pid_pvlist:
                self.check_waveform_PID_update_rate(pv_name, rate)

    def reset_data(self):
        self.reset_user_buffer()     
        self.user_buffer_pid_pv_data = {}
        self.user_buffer_pv_data = {}

    def format_array(self, array, threshold):
        # returns string of array to print

        leading_elements = preceding_elements = 3
        if len(array) > threshold:
            head_str = ' '.join(map(str, array[:leading_elements]))
            tail_str = ' '.join(map(str, array[-preceding_elements:]))
            return "[" + head_str + " ... " + tail_str + "] (" + str(len(array)) + ")"
        else:
            return "[" + ' '.join(map(str, array)) + "] (" + str(len(array)) + ")"
            

#### USER BUFFER MANIPULATION FUNCTIONS

    def prep_user_buffer(self, index, rate, fixed_rate=True, samples=1):
        # Assign global user buffer index
        settings.bsa_usr_buff_idx = index
        # Assign global user buffer rate
        settings.bsa_usr_buff_rate = rate
        # Assign global user buffer fixed rate flag
        settings.bsa_usr_buff_fixed_rate = fixed_rate

        # Assign global user buffer control and settings PVs
        # Get PVs to control and settings
        bsa_buff_prefix = settings.tpg.replace('TPG', 'BSA', 1)

        control_pv = bsa_buff_prefix + ':' + str(settings.bsa_usr_buff_idx) + ':CTRL'
        meascnt_pv = bsa_buff_prefix + ':' + str(settings.bsa_usr_buff_idx) + ':MEASCNT'
        rate_mode_pv = bsa_buff_prefix + ':' + str(settings.bsa_usr_buff_idx) + ':RATEMODE'           
        ac_rate_pv = bsa_buff_prefix + ':' + str(settings.bsa_usr_buff_idx) + ':ACRATE'           
        fixed_rate_pv = bsa_buff_prefix + ':' + str(settings.bsa_usr_buff_idx) + ':FIXEDRATE'

        # Assign control and others settings to global PVs too
        settings.bsa_usr_buff_rate_mode_pv = rate_mode_pv
        settings.bsa_usr_buff_ac_rate_pv = ac_rate_pv
        settings.bsa_usr_buff_fixed_rate_pv = fixed_rate_pv
        settings.bsa_usr_buff_control_pv = control_pv
        # Set the update rate in the user buffer in TPG
        if settings.bsa_usr_buff_fixed_rate:
            caput(rate_mode_pv, "Fixed Rate", wait=True)
            caput(fixed_rate_pv, rate, wait=True)
        else:
            caput(rate_mode_pv, "AC Rate", wait=True)
            caput(ac_rate_pv, rate, wait=True)
        # Assign number of samples
        caput(meascnt_pv, str(samples), wait=True)

    def trigger_user_buffer(self, control_pv):
        # Trigger BSA data acquisition
        caput(control_pv, "OFF", wait=True)
        caput(control_pv, "ON", wait=True)

    def reset_user_buffer(self):
        # Reset buffer rate and control settings
        caput(settings.bsa_usr_buff_rate_mode_pv, "Fixed Rate", wait=True)
        caput(settings.bsa_usr_buff_fixed_rate_pv, list(settings.bsa_usr_buff_fixed_rates.keys())[0], wait=True)
        caput(settings.bsa_usr_buff_ac_rate_pv, list(settings.bsa_usr_buff_ac_rates.keys())[0], wait=True)
        caput(settings.bsa_usr_buff_control_pv, "OFF", wait=True)

#### DATA ACQUISITION FUNCTIONS

    def get_pvs_data_pair(self, pvlist, rate):
        for pv_name in pvlist:
            self.user_buffer_pv_data[pv_name] = PV_DATA([],[])
            if settings.bsss_usr_buff_acq:
                camonitor(pv_name, callback=self.on_monitor_pair_bsss_buffer)
            else:
                camonitor(pv_name, callback=self.on_monitor_pair_usr_buffer)

        # bsa_buff_prefix = settings.tpg.replace('TPG', 'BSA', 1)
        # cnt_pv = bsa_buff_prefix + ':' + str(settings.bsa_usr_buff_idx) + ':CNT'
        # camonitor(cnt_pv, callback=self.on_monitor_cnt_pv)

        self.sample_num = 1
        self.trigger_user_buffer(settings.bsa_usr_buff_control_pv)
        print("Acquiring first samples for rate " + rate)
        self.wait(pvlist, acquisition_num = 1)

        self.sample_num = 2
        self.trigger_user_buffer(settings.bsa_usr_buff_control_pv)
        print("Acquiring second samples for rate " + rate)
        self.wait(pvlist, acquisition_num = 2)

        # camonitor_clear(cnt_pv)
        for pv_name in pvlist:
            camonitor_clear(pv_name)
        
    def wait(self, pvlist, acquisition_num):
        if settings.bsss_usr_buff_acq:
            self.wait_bsss(pvlist, acquisition_num)
        else:
            self.wait_bsa(pvlist, acquisition_num)

    def wait_bsa(self, pvlist, acquisition_num):
        loop = 0

        if settings.usr_buff_acq_mode == "elements":
            while True:
                time.sleep(1)
                if acquisition_num == 1 and all(len(value.signal_data1) >= settings.bsa_usr_buff_elements for value in self.user_buffer_pv_data.values()):
                    break
                elif acquisition_num == 2 and all(len(value.signal_data2) >= settings.bsa_usr_buff_elements for value in self.user_buffer_pv_data.values()):
                    break
        else:
            time.sleep(settings.bsa_usr_buff_max_time)

    def wait_bsss(self, pvlist, acquisition_num):
        loop = 0

        if settings.bsss_acq_mode == "elements":
            while True:
                time.sleep(1)
                if acquisition_num == 1 and all(len(value.signal_data1) >= settings.bsss_num_samples for value in self.user_buffer_pv_data.values()):
                    break
                elif acquisition_num == 2 and all(len(value.signal_data2) >= settings.bsss_num_samples for value in self.user_buffer_pv_data.values()):
                    break
        else:
            time.sleep(settings.bsss_max_time)
    
    def wait_pid_bsss(self, pid_pvlist):
        loop = 0

        if settings.bsss_acq_mode == "elements":
            while True:
                time.sleep(1)
                if all(len(value.signal_data1) >= settings.bsss_num_samples for value in self.user_buffer_pid_pv_data.values()):
                    break
        else:
            time.sleep(settings.bsss_max_time)

    def get_pvs_data_single(self, pid_pvlist, rate):
        print("Acquiring PV arrays for rate " + rate)
        for pv_name in pid_pvlist:
            self.user_buffer_pid_pv_data[pv_name] = PV_DATA([],[])
            camonitor(pv_name, callback=self.on_monitor_consec_scalar_usr_buff)

        self.trigger_user_buffer(settings.bsa_usr_buff_control_pv)

        self.wait_pid_bsss(pid_pvlist)
        
        for pv_name in pid_pvlist:
            camonitor_clear(pv_name)

    def on_monitor_consec_scalar_usr_buff(self, pvname=None, value=None, **kw):
        self.user_buffer_pid_pv_data[pvname].signal_data1.append(value)

    def on_monitor_pair_usr_buffer(self, pvname=None, value=None, **kw):
        if isinstance(value, float) and not settings.bsss_usr_buff_acq:
            value = [value]
        if self.sample_num == 1:
            self.user_buffer_pv_data[pvname].signal_data1 = value
        else: #sample number = 2
            self.user_buffer_pv_data[pvname].signal_data2 = value
    
    def on_monitor_cnt_pv(self, pvname=None, value=None, **kw):
        self.sample_size = value

    def on_monitor_pair_bsss_buffer(self, pvname=None, value=None, **kw):
        if isinstance(value, float) and not settings.bsss_usr_buff_acq:
            value = [value]
        if self.sample_num == 1:
            self.user_buffer_pv_data[pvname].signal_data1.append(value)
        else: #sample number = 2
            self.user_buffer_pv_data[pvname].signal_data2.append(value)

#### TESTING FUNCTIONS

    def check_waveform_PID_update_rate(self, pv_name, rate):
        update_rate = self.compute_PID_update_rate(pv_name)
        self.compare_PID_update_rate(pv_name, rate, update_rate)

    def check_number_of_elements_usr_buff(self, pv_name, samples):

        signal_data1 = self.user_buffer_pv_data[pv_name].signal_data1

        # if settings.usr_buff_acq_mode == "max_time":
        #     samples = self.sample_size
        # Compare number of elements
        if np.array(signal_data1).size > samples:
            self.logger.error("[ERROR]    - " + pv_name + " contains more than the expected number of elements.")
        elif np.array(signal_data1).size < samples:
            self.logger.error("[ERROR]    - " + pv_name + " contains fewer than the expected number of elements.")
        else:
            print("PV number of elements:       OK (" + str(np.array(signal_data1).size) + ")")

    def check_pv_for_updated_data(self, pv_name, pv_data):
        # Check to see if we always get the same value in the latest sample 
        if (isinstance(pv_data.signal_data2, (list, tuple, np.ndarray)) and (np.array(pv_data.signal_data2) == np.array(pv_data.signal_data2)[-1]).all()) or \
           (not isinstance(pv_data.signal_data2, (list, tuple, np.ndarray)) and (np.array(pv_data.signal_data2) == np.array([pv_data.signal_data2])[-1]).all()):
            self.logger.warning("[WARNING]  - " + pv_name + " keeps the same value over time.")
            self.logger.warning("             Is IOC triggering the firmware correctly?")
        else:
            print("PV Updated With New Data:    OK")

    def check_pair_for_diff_pv_data(self, pv_name, pv_data):
        # Check if the bsa buffers changed in time.
        if np.array_equal(np.array(pv_data.signal_data1), np.array(pv_data.signal_data2)) and np.array(pv_data.signal_data1).size != 0:
            self.logger.critical("[CRITICAL] - " + pv_name + " is not updated with new values.")
            self.logger.critical("             Sampling too fast or is the PV value constant?")
        else:
            print("Pair Of Samples Diff:        OK")

    def check_pair_for_packed_pv_data(self, pv_name, pv_data):
        # Check if both samples are populated with data
        if (                                                                                                     \
             (isinstance(pv_data.signal_data1, (list, tuple, np.ndarray)) and (len(pv_data.signal_data1) == 0))               or \
             (isinstance(pv_data.signal_data2, (list, tuple, np.ndarray)) and (len(pv_data.signal_data2) == 0))               or \
             (not isinstance(pv_data.signal_data1, (list, tuple, np.ndarray)) and (np.array(pv_data.signal_data1).size == 0)) or \
             (not isinstance(pv_data.signal_data2, (list, tuple, np.ndarray)) and (np.array(pv_data.signal_data2).size == 0))):
            self.logger.error("[ERROR] -    " + pv_name + " didn't bring any data (empty).")
            self.logger.error("             Is BSA working?")
            return True
        else:
            print("PV Populated With Data:      OK")
            return False

    def check_pv_for_nan_data(self, pv_name, pv_data):
        # Check for at least one NaN value
        if np.isnan(np.sum(pv_data.signal_data1)) or np.isnan(np.sum(pv_data.signal_data2)):
            self.logger.error("[ERROR]    - " + pv_name + " contains NaN values.")
        else:
            print("PV Does Not Have NaNs:       OK")

    def compare_PID_update_rate(self, pv_name, update_rate, diff):
        # We have a user buffer, extract update rate from buffer rate dictionary  
        pv_update_rate = update_rate
        pid_update_rate = settings.core_linac_freq / diff
        if diff == -1:
            self.logger.error("[ERROR] -    " + pv_name + " PID diffs are not consistent between elements")
            self.logger.error("             Please make sure that sampling of data is done at consistent intervals.")
            self.logger.error("             Ignore this error if firmware/IOC has just been rebooted.")
        elif diff == -2:
            self.logger.error("[ERROR] -    " + pv_name + " PID array is empty")
        elif not np.equal(pid_update_rate, pv_update_rate):
            self.logger.error("[ERROR] -    " + pv_name + " the PID update rate (" + str(pid_update_rate) + \
            "Hz) doesn't match the PV update rate of " + str(pv_update_rate) + "Hz")
            self.logger.error("             Please make sure that sampling of data is done at consistent intervals.")
        else:
            print("PID Update Rate:             OK (" + str(pid_update_rate) + "Hz)")

    def compute_PID_update_rate(self, pv_name):
        if settings.bsss_usr_buff_acq:
            signal_data = self.user_buffer_pid_pv_data[pv_name].signal_data1
            print("\nPID sample     --> " + self.format_array(signal_data, threshold = 15))
        else:
            signal_data = self.user_buffer_pv_data[pv_name].signal_data1
        if len(signal_data) == 0:
            return -2
        PID_data = list(reversed(signal_data))         
        prev_diff = PID_data[0] - PID_data[1]
        for i in range(2, len(PID_data)):
            prev_PID = PID_data[i-1]
            cur_PID = PID_data[i]
            diff = prev_PID - cur_PID
            if np.not_equal(diff, prev_diff):
                #PID update rate is inconsistent
                return -1
        return prev_diff