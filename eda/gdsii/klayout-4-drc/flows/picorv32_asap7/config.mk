# Paths refer to the read-only input snapshot mounted by flow.py.
export PLATFORM = asap7
export DESIGN_NAME = picorv32
export DESIGN_NICKNAME = picorv32_autofix
export VERILOG_FILES = /inputs/rtl/picorv32.v
export SDC_FILE = /inputs/constraint.sdc

# RV32IMC, native memory interface, iterative multiplier and divider.
export VERILOG_TOP_PARAMS = COMPRESSED_ISA 1 ENABLE_MUL 1 ENABLE_DIV 1 BARREL_SHIFTER 1
export SYNTH_USE_SYN = 0

# ASAP7 Liberty and SDC use ps. This is a 1 ns (1 GHz) target.
export CLOCK_PERIOD = 1000
export CORNER = TC
export ASAP7_USE_VT = RVT

export CORE_UTILIZATION = 40
export CORE_ASPECT_RATIO = 1
export CORE_MARGIN = 2
export PLACE_DENSITY = 0.55
export GPL_PLACE_IOS = 1
export TNS_END_PERCENT = 100
