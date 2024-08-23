# Atrium
Automated Test Regression for IOCs Under Measurement

## How To Run
Example: Run on cpu-b084-sp17 as shown below:

$ ./atrium --cpu cpu-b084-sp17 --tpg TPG:B084:2 --usr_buffs 21 --sys_buffs SCS --ioc sioc-b084-gd01 --bsa_usr_buff_elements 6  --bsss_num_samples 4 --bld_configs 1 2 --test_type all

## Arguments
- `-h`, `--help`  
  Show this help message and exit.

- `--cpu CPU`  
  CPU hosting the IOC to test.

- `--ioc IOC`  
  IOC to test.

- `--tpg TPG`  
  TPG base PV name (default: TPG:SYS0:1).
  
- `--usr_buffs USR_BUFF_LIST [USR_BUFF_LIST ...]`  
  List of user buffers to test (default to all buffers).

- `--sys_buffs SYS_BUFF_LIST [SYS_BUFF_LIST ...]`  
  List of system buffers to test (default to all buffers).

- `--bsa_usr_buff_elements BSA_USR_BUFF_ELEMENTS`  
  Number of user buffer elements to acquire (default for waveform: 2).

- `--bsa_usr_buff_max_time BSA_USR_BUFF_MAX_TIME`  
  Max time for user buffer acquisition (seconds).

- `--bsss_num_samples BSSS_NUM_SAMPLES`  
  Number of BSSS samples to acquire (default: 2).

- `--bsss_max_time BSSS_MAX_TIME`  
  Max time for BSSS to acquire (seconds).

- `--test_type TEST_TYPE`  
  Test type to run:
  - `sys`: Test only system buffers.
  - `usr`: Test only user buffers.
  - `bld`: Test only BLD frequencies.
  - `all`: Test all.

- `--bld_decode_path BLD_DECODE_PATH`  
  Path to file location of bldDecode (default: $PACKAGE_SITE_TOP/bldDecode/current).

- `--bld_configs BLD_CONFIGS [BLD_CONFIGS ...]`  
  List of BLD frequencies to test (default to all frequencies 1-4).
