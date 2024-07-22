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

        # Key: PV name; value: PV data
        self.user_buffer_pv_data = {}
        self.user_buffer_pid_pv_data = {} 
        self.user_buffer_new_sample_data = {}

        self.logger = settings.logger
        self.sample_number = 1

#### CORE FUNCTIONS

    def test_bsss_user_buffers(self):
        print("Checking BSSS user buffers.")
        settings.bsss_usr_buff_acq = True
        list_of_signal_pvs = settings.service_pv_prefixes["BSSS"]

        self.core_test_user_buffers(list_of_signal_pvs, settings.bsss_scalar_type_suffixes, settings.bsss_usr_buff_idx_range, 
        settings.bsss_usr_buff_fixed_rates, samples = 1)

    def test_bsa_user_buffers(self):
        print("Checking BSA user buffers.")
        settings.bsss_usr_buff_acq = False
        list_of_signal_pvs = settings.service_pv_prefixes["BSA"]

        self.core_test_user_buffers(list_of_signal_pvs, settings.bsa_hst_type_suffixes,
        settings.bsa_usr_buff_idx_range, settings.bsa_usr_buff_fixed_rates, samples=settings.bsa_usr_buff_samples_num_elem_test)

    def core_test_user_buffers(self, signal_pvs, variable_type_suffixes, usr_buff_idx_range, usr_buff_fixed_rates, samples):
        for idx in usr_buff_idx_range:
            print("\n------------------------")
            print("Testing User Buffer " + str(idx))
            print("------------------------")

            # Get PVs that will be tested and another list including only PID PV's
            pvlist, pid_pvlist = self.get_pv_lists(idx, signal_pvs, variable_type_suffixes)

            # Acquire data of all pv's that will be used for testing
            self.get_pvs_data(idx, pvlist, pid_pvlist, samples, usr_buff_fixed_rates)

            # Run tests for all user buffers
            self.run_tests(samples, pid_pvlist, usr_buff_fixed_rates)

            # Resets user data and data for pv lists
            self.reset_data()

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

    def get_pvs_data(self, idx, pvlist, pid_pvlist, samples, usr_buff_fixed_rates):
        self.prep_user_buffer(idx, samples=samples)
        self.get_pvs_data_pair(pvlist)
        sample_num = samples
        if settings.bsss_usr_buff_acq:
            sample_num = 2
        self.get_pvs_data_single(pid_pvlist, sample_num, idx, usr_buff_fixed_rates)
        self.get_pvs_new_sample(pvlist, samples, idx)

    def run_tests(self, samples, pid_pvlist, usr_buff_fixed_rates):
        for pv_name, pv_data in self.user_buffer_pv_data.items(): 
            print("\n*****<< " + pv_name + " >>*****\n")
            print("First sample   --> "+str(pv_data.signal_data1))
            print("Second sample  --> "+str(pv_data.signal_data2))
            
            # Test 1: check for signal change over time
            self.check_signal_change_over_time(pv_name, pv_data)

            # Test 2: check if the PID changes as expected (for a PID-type PV only)
            if pv_name in pid_pvlist:
                self.check_waveform_PID_update_rate(pv_name, usr_buff_fixed_rates)

            # Test 3: check if the acquired number of samples matches what is expected
            self.check_number_of_elements_usr_buff(pv_name, samples)

    def reset_data(self):
        self.reset_user_buffer()     
        self.user_buffer_pid_pv_data = {}
        self.user_buffer_pv_data = {}
        self.user_buffer_new_sample_data = {}

#### USER BUFFER MANIPULATION FUNCTIONS

    def prep_user_buffer(self, index, rate=list(settings.bsa_usr_buff_fixed_rates.keys())[0], fixed_rate=True, samples=1):
        # Assign global user buffer index
        settings.bsa_usr_buff_idx = index
        # Assign global user buffer rate
        settings.bsa_usr_buff_rate = rate
        # Assign global user buffer fixed rate flag
        settings.bsa_usr_buff_fixed_rate = fixed_rate
        # Assign global user buffer samples to acquire
        settings.bsa_usr_buff_samples = samples
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
    def get_pvs_data_pair(self, pvlist):
        for pv_name in pvlist:
            self.user_buffer_pv_data[pv_name] = PV_DATA([],[])
            camonitor(pv_name, callback=self.on_monitor_pair_usr_buffer)

        self.sample_number = 1
        self.trigger_user_buffer(settings.bsa_usr_buff_control_pv)
        print("Acquiring first samples for PV's.")
        self.wait(pvlist, wait_count = 1)

        self.sample_number = 2
        self.trigger_user_buffer(settings.bsa_usr_buff_control_pv)
        print("Acquiring second samples for PV's.")
        self.wait(pvlist, wait_count = 2)

        for pv_name in pvlist:
            camonitor_clear(pv_name)

    def wait(self, pvlist, wait_count):
        while True:
            time.sleep(settings.bsa_usr_buff_wait_time_per_sample * settings.bsa_usr_buff_samples)
            all_pvs_data_acquired = True
            for pv_name in pvlist:

                if settings.bsss_usr_buff_acq:
                    if (wait_count == 1 and len(self.user_buffer_pv_data[pv_name].signal_data1) != 1) \
                    or (wait_count == 2 and len(self.user_buffer_pv_data[pv_name].signal_data2) != 1):
                        all_pvs_data_acquired = False
                elif (wait_count == 1 and len(self.user_buffer_pv_data[pv_name].signal_data1) < settings.bsa_usr_buff_samples) \
                or (wait_count == 2 and len(self.user_buffer_pv_data[pv_name].signal_data2) < settings.bsa_usr_buff_samples):
                    all_pvs_data_acquired = False
            if all_pvs_data_acquired:
                break

    def get_pvs_data_single(self, pid_pvlist, samples, idx, usr_buff_fixed_rates):
        self.sample_number = 0
        for pv_name in pid_pvlist:
            self.user_buffer_pid_pv_data[pv_name] = PV_DATA([[] for _ in range(len(usr_buff_fixed_rates))],[])

            if settings.bsss_usr_buff_acq:
                camonitor(pv_name, callback=self.on_monitor_consec_scalar_usr_buff)
            else:
                camonitor(pv_name, callback=self.on_monitor_single_usr_buffer)

        print("Acquiring samples for PID PVs for rate:")
        for rate in usr_buff_fixed_rates.keys():
            print(rate)
            self.sample_number += 1
            self.prep_user_buffer(idx, rate, samples = samples)
            self.trigger_user_buffer(settings.bsa_usr_buff_control_pv)
            time.sleep(settings.bsa_usr_buff_wait_time_per_sample * settings.bsa_usr_buff_samples)

        for pv_name in pid_pvlist:
            camonitor_clear(pv_name)
        
    def get_pvs_new_sample(self, pid_pvlist, samples, idx):
        print("Acquiring new samples for PV's.")
        for pv_name in pid_pvlist:
            self.user_buffer_new_sample_data[pv_name] = PV_DATA([],[])
            camonitor(pv_name, callback=self.on_monitor_new_sample_usr_buffer)

        self.prep_user_buffer(idx, samples = samples)
        self.trigger_user_buffer(settings.bsa_usr_buff_control_pv)
        time.sleep(settings.bsa_usr_buff_wait_time_per_sample * settings.bsa_usr_buff_samples)

        for pv_name in pid_pvlist:
            camonitor_clear(pv_name)

    def on_monitor_new_sample_usr_buffer(self, pvname=None, value=None, **kw):
        self.user_buffer_new_sample_data[pvname].signal_data1 = [value]

    def on_monitor_single_usr_buffer(self, pvname=None, value=None, **kw):
        self.user_buffer_pid_pv_data[pvname].signal_data1[self.sample_number - 1] = value

    def on_monitor_consec_scalar_usr_buff(self, pvname=None, value=None, **kw):
        self.user_buffer_pid_pv_data[pvname].signal_data1[self.sample_number - 1].append(value)

    def on_monitor_pair_usr_buffer(self, pvname=None, value=None, **kw):
        if self.sample_number == 1:
            self.user_buffer_pv_data[pvname].signal_data1 = [value]
        else: #sample number = 2
            self.user_buffer_pv_data[pvname].signal_data2 = [value]

#### TESTING FUNCTIONS

    def check_signal_change_over_time(self, pv_name, pv_data): #check waveform signal change in time for pvlist
        self.check_pv_for_nan_data(pv_name, pv_data)
        # Check if both samples are populated with data
        self.check_pair_for_packed_pv_data(pv_name, pv_data)
        # Check if the bsa buffers changed in time.
        self.check_pair_for_diff_pv_data(pv_name, pv_data)
        # Check to see if we always get the same value in the latest sample 
        if not settings.bsss_usr_buff_acq:
            self.check_pv_for_updated_data(pv_name, pv_data)

    def check_waveform_PID_update_rate(self, pv_name, usr_buff_fixed_rates):
        print("\nChecking PID rate:\n")
        for index, (rate_key, rate_value) in enumerate(usr_buff_fixed_rates.items()):
            print("Fixed Rate = " + str(rate_key))
            update_rate = self.compute_PID_update_rate(pv_name, index)
            self.compare_PID_update_rate(pv_name, rate_value, update_rate)

    def check_number_of_elements_usr_buff(self, pv_name, samples):
        signal_data1 = self.user_buffer_new_sample_data[pv_name].signal_data1
        print("\nNew sample --> " + str(signal_data1) )
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
        else:
            print("PV Populated With Data:      OK")

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
        if not np.equal(pid_update_rate, pv_update_rate):
            self.logger.error("[ERROR] -    " + pv_name + " the PID update rate (" + str(pid_update_rate) + \
            "Hz) doesn't match the PV update rate of " + str(pv_update_rate) + "Hz")
            self.logger.error("             Please make sure that sampling of data is done at consistent intervals.")
        else:
            print("PID Update Rate:             OK  (" + str(pid_update_rate) + "Hz)")

    def compute_PID_update_rate(self, pv_name, index):
        signal_data = self.user_buffer_pid_pv_data[pv_name].signal_data1[index]
        print("Sample acquired --> " + str(signal_data))
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