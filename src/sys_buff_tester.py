import time
import numpy as np
import settings

from epics import caget, caput, camonitor, camonitor_clear, PV

#************ BSA_TESTER Class ************#
class SYS_BUFF_TESTER:
    """
    
    This class will test the BSA buffers.

    """

    def __init__(self):
        print("Initializing BSA_TESTER\n")
        
        self.logger = settings.logger
        
        self.signal_data1 = []
        self.signal_data2 = []
        self.sample_num = 1

    def core_test_system_buffers(self, signal_pvs, variable_type_suffixes, fcn_check_signal_change_in_time, fcn_check_PID_update_rate):
        for dest_suffix in settings.system_buff_dest_suffixes:
            for freq_suffix, freq in settings.system_buff_freq_suffixes.items():

                proceed = self.skip_destination(dest_suffix, freq_suffix)
                        
                if proceed or settings.sys_buff_list == []:
                    print("\n--------------")
                    print("Testing " + dest_suffix + freq_suffix) 
                    print("--------------")

                    for signal_pv in signal_pvs:
                        for var_type in variable_type_suffixes: 
                            # Form the PV name
                            pv = signal_pv + var_type + dest_suffix + freq_suffix
                            print("\n*****<< " + pv + " >>*****\n")
                            # Start running tests for PV
                            # Test 1: check for signal change over time
                            fcn_check_signal_change_in_time(pv_name=pv)
                            
                            # Test 2: check if the PID changes as expected (for a PID-type PV only)
                            if "PID" in pv:
                                print("\nChecking PID rate:\n")
                                fcn_check_PID_update_rate(pv_name=pv) 

    def skip_destination(self, dest_suffix, freq_suffix):
        # Check if the user requested a subset of system buffers to test
        proceed = False
        for k in settings.sys_buff_list:
            if not proceed:
                proceed = k in (dest_suffix + freq_suffix)
        return proceed

    def reset_data(self):
        self.signal_data1 = []
        self.signal_data2 = []
        self.sample_num = 1

    def on_monitor_single_sys_buff(self, pvname=None, value=None, **kw):
        if len(self.signal_data1) == 0:
            self.signal_data1 = value

    def on_monitor_pair_sys_buff(self, pvname=None, value=None, **kw):
        if len(self.signal_data1) == 0:
            self.signal_data1 = value
        elif len(self.signal_data2) == 0:
            self.signal_data2 = value

    def on_monitor_pair_bsss_sys_buff(self, pvname=None, value=None, **kw):
        if self.sample_num == 1 and len(self.signal_data1) < settings.bsss_num_samples:
            self.signal_data1.append(value)
        elif self.sample_num == 2 and len(self.signal_data2) < settings.bsss_num_samples:
            self.signal_data2.append(value)

    def on_monitor_single_bsss_sys_buff(self, pvname=None, value=None, **kw):
        if self.sample_num == 1 and len(self.signal_data1) < settings.bsss_num_samples:
            self.signal_data1.append(value)

    def get_pv_data_single(self, pv_name):
        # Prepare global variables for write access 
        self.reset_data()

        # System buffer
        pv = PV(pv_name)
        pv.wait_for_connection(timeout=None)
        if np.array(pv.value).size > 0:
            # Scalar/Waveform PV
            if settings.bsss_sys_buff_acq:
                cb = pv.add_callback(callback=self.on_monitor_single_bsss_sys_buff)
            else:
                cb = pv.add_callback(callback=self.on_monitor_single_sys_buff)

            if settings.bsss_sys_buff_acq:
                self.sample_num = 1
                self.wait(self.sample_num)
            else:
                while len(self.signal_data1) == 0:
                    time.sleep(settings.sys_buff_wait_time)
            
            pv.remove_callback(cb) 
            print("Reading sample --> "+ self.format_array(self.signal_data1, threshold = 15))
            return True
        else:
            # Empty PV
            self.logger.error("[ERROR] -    " + pv_name + " is empty!!")
            return False

    def get_pv_data_pair(self, pv_name): 
        # Prepare global variables for write access
        self.reset_data()

        # System buffer
        pv = PV(pv_name)
        pv.wait_for_connection(timeout=None)
        if np.array(pv.value).size > 0:
            # Scalar/Waveform PV
            if settings.bsss_sys_buff_acq:
                cb = pv.add_callback(callback=self.on_monitor_pair_bsss_sys_buff)
            else:
                cb = pv.add_callback(callback=self.on_monitor_pair_sys_buff)

            if settings.bsss_sys_buff_acq:
                self.sample_num = 1
                self.wait(self.sample_num)
                self.sample_num = 2
                self.wait(self.sample_num)
            else:
                while len(self.signal_data1) == 0 or len(self.signal_data2) == 0:
                    time.sleep(settings.sys_buff_wait_time)

            pv.remove_callback(cb) 
            print("First sample   --> "+ self.format_array(self.signal_data1, threshold = 15))
            print("Second sample  --> "+ self.format_array(self.signal_data2, threshold = 15))
            return True
        else:
            # Empty PV
            self.logger.error("[ERROR] -    " + pv_name + " is empty!!")
            return False

    def wait(self, acquisition_num):
        if settings.bsss_acq_mode == "time":
            start = time.time()
        while True:
            time.sleep(0.5)
            if acquisition_num == 1 and len(self.signal_data1) >= settings.bsss_num_samples:
                break
            if acquisition_num == 2 and len(self.signal_data2) >= settings.bsss_num_samples:
                break
            current = time.time()
            if settings.bsss_acq_mode == "time" and (current - start) > settings.bsss_max_time:
                break

    def compute_waveform_PID_update_rate(self):
        #PID data from farthest away to most recent
        PID_data = list(reversed(self.signal_data1))         
        prev_diff = PID_data[0] - PID_data[1]
        for i in range(2, len(PID_data)):
            prev_PID = PID_data[i-1]
            cur_PID = PID_data[i]
            diff = prev_PID - cur_PID
            if np.not_equal(diff, prev_diff):
                #PID update rate is inconsistent
                return -1
        return prev_diff

    def compute_scalar_PID_update_rate(self):
        ppid = self.signal_data1
        pid  = self.signal_data2
        return pid - ppid

    def compare_waveform_PID_update_rate(self, pv_name, diff):
        sys_buff_match = [k for k in list(settings.system_buff_freq_suffixes.keys()) if k in pv_name]
        if sys_buff_match and not settings.bsa_usr_buff:
            # We have a system buffer, extract update rate from name
            pv_update_rate  = settings.system_buff_freq_suffixes[sys_buff_match[0]]
            pid_update_rate = settings.core_linac_freq / diff
            if diff == -1:
                self.logger.error("[ERROR] -    In " + pv_name + " the PID diffs are not consistent between elements")
                self.logger.error("             Please make sure that sampling of data is done at consistent intervals.")
                self.logger.error("             Ignore this error if firmware/IOC has just been rebooted.")
            elif not np.equal(pid_update_rate, pv_update_rate):
                self.logger.error("[ERROR] -    " + pv_name + " the PID update rate (" + str(pid_update_rate) + \
                "Hz) doesn't match the PV update rate of " + str(pv_update_rate) + "Hz")
                self.logger.error("             Please make sure that sampling of data is done at consistent intervals.")
            else:
                print("PID Update Rate:             OK  (" + str(pid_update_rate) + "Hz)")

    def compare_scalar_PID_update_rate(self, pv_name, diff):
        self.compare_waveform_PID_update_rate(pv_name, diff)

    def check_pair_for_packed_pv_data(self, pv_name):
        # Check if both samples are populated with data
        if (                                                                                                     \
             (isinstance(self.signal_data1, (list, tuple, np.ndarray)) and (len(self.signal_data1) == 0))               or \
             (isinstance(self.signal_data2, (list, tuple, np.ndarray)) and (len(self.signal_data2) == 0))               or \
             (not isinstance(self.signal_data1, (list, tuple, np.ndarray)) and (np.array(self.signal_data1).size == 0)) or \
             (not isinstance(self.signal_data2, (list, tuple, np.ndarray)) and (np.array(self.signal_data2).size == 0))):
            self.logger.error("[ERROR] -    " + pv_name + " didn't bring any data (empty).")
            self.logger.error("             Is BSA working?")
            return False
        else:
            print("PV Populated With Data:      OK")
            return True

    def check_pair_for_diff_pv_data(self, pv_name):
        # Check if the bsa buffers changed in time.
        if np.array_equal(np.array(self.signal_data1), np.array(self.signal_data2)) and np.array(self.signal_data1).size != 0:
            self.logger.critical("[CRITICAL] - " + pv_name + " is not updated with new values.")
            self.logger.critical("             Sampling too fast or is the PV value constant?")
        else:
            print("Pair Of Samples Diff:        OK")

    def check_pv_for_updated_data(self, pv_name):
        # Check to see if we always get the same value in the latest sample 
        if (isinstance(self.signal_data2, (list, tuple, np.ndarray)) and (np.array(self.signal_data2) == np.array(self.signal_data2)[-1]).all()) or \
           (not isinstance(self.signal_data2, (list, tuple, np.ndarray)) and (np.array(self.signal_data2) == np.array([self.signal_data2])[-1]).all()):
            self.logger.warning("[WARNING]  - " + pv_name + " keeps the same value over time.")
            self.logger.warning("             Is IOC triggering the firmware correctly?")
        else:
            print("PV Updated With New Data:    OK")

    def check_pv_for_nan_data(self, pv_name):
        # Check for at least one NaN value
        if np.isnan(np.sum(self.signal_data1)) or np.isnan(np.sum(self.signal_data2)):
            self.logger.error("[ERROR]    - " + pv_name + " contains NaN values.")
        else:
            print("PV Does Not Have NaNs:       OK")

    def check_waveform_signal_change_in_time(self, pv_name):
        # Sample PV data
        success = self.get_pv_data_pair(pv_name)
        if not success:
            return
        # Check if both samples are populated with data
        self.check_pair_for_packed_pv_data(pv_name)
        # Check for NaN values
        self.check_pv_for_nan_data(pv_name)
        # Check if the bsa buffers changed in time.
        self.check_pair_for_diff_pv_data(pv_name)
        # Check to see if we always get the same value in the latest sample 
        self.check_pv_for_updated_data(pv_name)
    
    def check_scalar_signal_change_in_time(self, pv_name):
        # Sample PV data
        success = self.get_pv_data_pair(pv_name)
        if not success:
            return
        # Check if both samples are populated with data
        self.check_pair_for_packed_pv_data(pv_name)
        # Check for NaN values
        self.check_pv_for_nan_data(pv_name)
        # Check if the bsa buffers changed in time.
        self.check_pair_for_diff_pv_data(pv_name)

    def check_waveform_PID_update_rate(self, pv_name):
        if "PID" in pv_name:
            # Sample PID PV data
            success = self.get_pv_data_single(pv_name)
            if not success:
                return
            # Extract PID update rate
            rate = self.compute_waveform_PID_update_rate()
            # Compare with expected PID update rate
            self.compare_waveform_PID_update_rate(pv_name, rate)
    
    def check_scalar_PID_update_rate(self, pv_name):
        if "PID" in pv_name and "HST" not in pv_name:
            if not settings.bsa_usr_buff:
                # Sample PID PV data
                success = self.get_pv_data_pair(pv_name)
                if not success:
                    return
                # Extract PID update rate
                rate = self.compute_scalar_PID_update_rate() 
                # Compare with expected PID update rate
                self.compare_scalar_PID_update_rate(pv_name, rate)
            elif settings.bsa_usr_buff:
                # To verify PID rate, get one waveform sample with consecutive PIDs
                success = self.get_pv_data_single(pv_name)
                if not success:
                    return
                # Extract PID update rate
                rate = self.compute_waveform_PID_update_rate()
                # Compare with expected PID update rate
                self.compare_waveform_PID_update_rate(pv_name, rate)

    def test_bsa_system_buffers(self):
        settings.bsss_sys_buff_acq = False
        print("Checking BSA system buffers.")
        list_of_signal_pvs = settings.service_pv_prefixes["BSA"]
        self.core_test_system_buffers(list_of_signal_pvs, settings.bsa_hst_type_suffixes,
        self.check_waveform_signal_change_in_time, self.check_waveform_PID_update_rate)

    def test_bsss_system_buffers(self):
        settings.bsss_sys_buff_acq = True
        print("Checking BSSS system buffers.")
        list_of_signal_pvs = settings.service_pv_prefixes["BSSS"]
        self.core_test_system_buffers(list_of_signal_pvs, settings.bsss_scalar_type_suffixes,
        self.check_waveform_signal_change_in_time, self.check_waveform_PID_update_rate)

    def format_array(self, array, threshold):
        # returns string of array to print
        leading_elements = preceding_elements = 3
        if len(array) > threshold:
            head_str = ', '.join(map(str, array[:leading_elements]))
            tail_str = ', '.join(map(str, array[-preceding_elements:]))
            return "[" + head_str + " ... " + tail_str + "] (" + str(len(array)) + ")"
        else:
            return "[" + ', '.join(map(str, array)) + "] (" + str(len(array)) + ")"

    # def test_bsa_fault_buffers(self):
    #     print("Checking BSA fault buffers.")
    #     list_of_signal_pvs = settings.service_pv_prefixes["BSA"]
    #     self.core_test_fault_buffers(list_of_signal_pvs, settings.bsa_hst_type_suffixes,
    #     settings.flt_buff_suffixes, self.check_waveform_signal_change_in_time) 
    
    # def test_bsss_fault_buffers(self):
    #     print("Checking BSSS fault buffers - There are no BSSS fault buffers.")
    #     print("                              Nothing else to do here. Moving on.")

    # def core_test_fault_buffers(self, signal_pvs, variable_type_suffixes, flt_buff_name_suffixes, fcn_check_signal_change_in_time):
    # for signal_pv in signal_pvs:
    #     print("\n---------------------------------------------")
    #     print("Testing " + " for " + signal_pv)
    #     print("---------------------------------------------")
    #     for var_type in variable_type_suffixes:
    #         for flt_idx_suffix in flt_buff_name_suffixes:
    #             # Form the PV name
    #             pv = signal_pv + var_type + flt_idx_suffix
    #             print("\n*****<< " + pv + " >>*****\n")
                    
    #             # Test 1: check for signal change over time
    #             fcn_check_signal_change_in_time(pv)