# Export trusted net identities from ODB. Works in OpenROAD without Python support.
proc c2c3_json_string {value} {
  return "\"[string map [list "\\" "\\\\" "\"" "\\\"" "\n" "\\n" "\r" "\\r" "\t" "\\t"] $value]\""
}
read_db $::env(C2C3_INPUT_ODB)
set block [ord::get_db_block]
set die [$block getDieArea]
set output [open $::env(C2C3_NETS_JSON) w]
puts $output [format {{"kind":"metadata","dbu_per_um":%d,"die_dbu":[%d,%d,%d,%d],"instance_count":%d}} \
  [$block getDbUnitsPerMicron] [$die xMin] [$die yMin] [$die xMax] [$die yMax] [llength [$block getInsts]]]
foreach net [$block getNets] {
  set iterms {}
  set bterms {}
  set clock_terminal false
  foreach term [$net getITerms] {
    set master_term [$term getMTerm]
    set pin_name [$master_term getName]
    if {[$master_term getSigType] eq "CLOCK" || $pin_name in {CLK CK CP CLKIN CLKOUT}} {
      set clock_terminal true
    }
    lappend iterms [format {[%s,%s]} [c2c3_json_string [[$term getInst] getName]] [c2c3_json_string $pin_name]]
  }
  foreach term [$net getBTerms] {
    lappend bterms [c2c3_json_string [$term getName]]
  }
  puts $output [format {{"kind":"net","name":%s,"signal_type":%s,"clock_terminal":%s,"has_wire":%s,"iterms":[%s],"bterms":[%s]}} \
    [c2c3_json_string [$net getName]] [c2c3_json_string [$net getSigType]] $clock_terminal \
    [expr {[$net getWire] eq "NULL" ? "false" : "true"}] [join $iterms ,] [join $bterms ,]]
}
close $output
