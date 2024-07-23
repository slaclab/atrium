import logging
import numpy as np

############################################
#             Global variables             #
############################################

# The BSA suffix for the system buffers are a combination of the destination
# suffix with the frequency suffix and the HST string. Example: HSTSCHTH
# The user buffers are just a number as suffix, so we are not using lists or
# dictionaries to represent them.

# SCD = SuperConducting to Diag0
# SCL = SuperConducting to Linac (BSY + HXR + SXR)
# SCB = SuperConducting to SC BSY Dump
# SCH = SuperConducting to Hard x-ray beamline 
# SCS = SuperConducting to Soft x-ray beamline 
system_buff_dest_suffixes = ["SCD", "SCL", "SCB", "SCH", "SCS"]

# Dictionary that relates the frequency rate with the end of the system buffer name
system_buff_freq_suffixes = {"1H": 1, "TH": 10, "HH": 100}

# Types of data/metadata to be stored in BSA PVs
# For now let's comment CNT and RMS because they need special test cases.
#bsa_hst_type_suffixes = ["HST","CNTHST","RMSHST","PIDHST"] 
bsa_hst_type_suffixes = ["HST","PIDHST"] 

# Types of data/metadata to be stored in BSSS PVs
bsss_scalar_type_suffixes = ["","PID"] 

# All types of data/metadata to be stored in BSA/BSSS PVs
acq_type_suffixes = bsa_hst_type_suffixes + bsss_scalar_type_suffixes

# BSA user buffer flag
bsa_usr_buff = False 

# BSA user buffer index (index, 21...49)
bsa_usr_buff_idx = 21

# BSA user buffer rate 
bsa_usr_buff_rate = "1Hz" 

# BSA user buffer samples to acquire
bsa_usr_buff_samples = 1                # initialize to a non-zero value
bsa_usr_buff_samples_num_elem_test = 2  # at least two are needed for a waveform PV

# BSA user buffer max time to wait acquiring samples (seconds)
# bsa_buff_max_time = 50

# Wait time for a BSA user buffer to acquire one sample
bsa_usr_buff_wait_time_per_sample = 1

# BSA user buffer control and settings PVs
bsa_usr_buff_rate_mode_pv  = ""
bsa_usr_buff_ac_rate_pv    = ""
bsa_usr_buff_fixed_rate_pv = ""
bsa_usr_buff_control_pv    = "" 

# BSA user buffer fixed rate flag
bsa_usr_buff_fixed_rate = True 

# BSA user buffer index range
bsa_usr_buff_idx_range = np.arange(21,50)

# BSA user buffer fixed rate options
# Because of roundings, we need to force 71.5kHz to 7.0e+4. PID difference
# returns 13, but the most accurate should be 12.73.
# 1MHz is also forced to 9.1e+5 because the accurate diff would be 0.91,
# but diff comes back as 1.
bsa_usr_buff_fixed_rates  = {"1Hz":1,"10Hz":10,"100Hz":100,"1kHz":1.0e+03,"10kHz":10.0e+03,"71.5kHz":7.0e+04,"1MHz":9.1e+05}

# BSA user buffer AC rate options
bsa_usr_buff_ac_rates = {"0.5Hz":0.5,"1Hz":1,"5Hz":5,"10Hz":10,"30Hz":30,"60Hz":60}

# Wait time to acquire from a system buffer
sys_buff_wait_time = 1 

# BSSS user buffer index range
bsss_usr_buff_idx_range = bsa_usr_buff_idx_range

# BSSS user buffer fixed rate options
bsss_usr_buff_fixed_rates = {"1Hz":1,"10Hz":10,"100Hz":100}

# BSSS data collection format
bsss_usr_buff_acq = False

# Fault buffer suffixes 
flt_buff_suffixes = ["FLTB0","FLTB1","FLTB2","FLTB3"] 

# Holds the specific PV prefix used by the IOC for each signal. Example: TST:SYS2:4:SIGNAL01
service_pv_prefixes = {"BSA": [], "BSSS": [], "BSAS": [], "BLD": []}

# Main beam frequency, assume LCLS-II/SC (910kHz)
core_linac_freq = 910000

# CPU name
cpu = ""

# IOC name
ioc = ""

# TPG PV prefix
tpg = ""

# This may be modified by the user
sys_buff_list = []

# Environment path variables from st.cmd and envPaths
cmd_env_paths = {}

# Number of loops to wait for data acquisition before timing out
loop_timeout = 3

# Test user buffer/sys buffer or both
test_type = ""


##  TPG Table Below
##  -------     ------------------------
##  TPG ioc     TPG Prefix 
##  -------     ------------------------ 
##  B34 TPG     GLOBAL=TPG:SYS0:1   (default for B34 TPG and LCLS2 production)
##  B84 TPG     GLOBAL=TPG:SYS0:2
##  B15 TPG     GLOBAL=TPG:B015:1
##  -------     ------------------------

# Logger object - CRITICAL, ERROR, WARNING, INFO, DEBUG
logger = logging.getLogger()
file_handler = logging.FileHandler("logfile.log", mode='w')
file_handler.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)

