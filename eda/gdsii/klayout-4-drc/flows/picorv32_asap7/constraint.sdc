set_units -time ps -capacitance fF -resistance kOhm -voltage V -current mA -power pW
current_design picorv32

set clk_period 1000
set io_delay [expr 0.20 * $clk_period]
create_clock -name core_clock -period $clk_period [get_ports clk]
create_clock -name io_clock -period $clk_period
set_input_delay $io_delay -clock io_clock [all_inputs -no_clocks]
set_output_delay $io_delay -clock io_clock [all_outputs]
set_max_fanout 16 [current_design]

# resetn is synchronous. Keep its input timing checks enabled.
