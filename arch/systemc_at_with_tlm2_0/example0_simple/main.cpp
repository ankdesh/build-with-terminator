#include <systemc>
#include "initiator_a.h"
#include "pipeline_b.h"
#include "target_c.h"
#include <string>

int sc_main(int argc, char* argv[]) {
    int scenario = 1;
    if (argc > 1) {
        try {
            scenario = std::stoi(argv[1]);
        } catch (...) {
            std::cerr << "Invalid scenario argument, defaulting to 1.\n";
            scenario = 1;
        }
    }

    InitiatorA initiator("initiator_a", scenario);
    PipelineB pipeline("pipeline_b");
    TargetC target("target_c");

    // Bind sockets
    initiator.socket.bind(pipeline.target_socket);
    pipeline.initiator_socket.bind(target.socket);

    // Setup VCD Waveform Tracing
    std::string vcd_name = "example0_sc" + std::to_string(scenario);
    sc_core::sc_trace_file* tf = sc_core::sc_create_vcd_trace_file(vcd_name.c_str());
    if (tf) {
        tf->set_time_unit(1, sc_core::SC_NS); // Set VCD time resolution to 1ns
        pipeline.register_trace(tf, "top.pipeline_b");
    }

    std::cout << "[CYCLE: 0] [SYSTEM] Starting Example 0: Simple Pipeline Stage (AT) - Scenario " << scenario << " ===\n";
    sc_core::sc_start(120, sc_core::SC_NS); // Run for 12 cycles
    std::cout << "[CYCLE: 12] [SYSTEM] Example 0 Finished ===\n";

    // Close trace file
    if (tf) {
        sc_core::sc_close_vcd_trace_file(tf);
        std::cout << "[SYSTEM] Waveform dumped successfully to " << vcd_name << ".vcd\n";
    }

    return 0;
}
