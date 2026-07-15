#include <systemc>
#include <vector>
#include <memory>
#include <string>
#include "initiator.h"
#include "target_node.h"
#include "switch_target.h"

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

    // Instantiate 4 Initiators with scenario
    std::vector<std::unique_ptr<Initiator>> initiators;
    for (int i = 0; i < 4; ++i) {
        std::string name = "initiator_" + std::to_string(i);
        initiators.push_back(std::make_unique<Initiator>(name.c_str(), i, scenario));
    }

    // Instantiate 1 Switch Target
    SwitchTarget switch_unit("switch");

    // Instantiate 4 Target Nodes
    std::vector<std::unique_ptr<TargetNode>> target_nodes;
    for (int i = 0; i < 4; ++i) {
        std::string name = "target_" + std::to_string(i);
        target_nodes.push_back(std::make_unique<TargetNode>(name.c_str(), i));
    }

    // Bind sockets using multi-socket binding
    for (int i = 0; i < 4; ++i) {
        initiators[i]->socket.bind(switch_unit.target_sockets);
        switch_unit.initiator_sockets.bind(target_nodes[i]->socket);
    }

    // Setup VCD Waveform Tracing
    std::string vcd_name = "example3_sc" + std::to_string(scenario);
    sc_core::sc_trace_file* tf = sc_core::sc_create_vcd_trace_file(vcd_name.c_str());
    if (tf) {
        tf->set_time_unit(1, sc_core::SC_NS); // Set VCD time resolution to 1ns
        switch_unit.register_trace(tf, "top.switch");
    }

    std::cout << "[CYCLE: 0] [SYSTEM] Starting Example 3: Shared Switch Arbitration (AT) - Scenario " << scenario << " ===\n";
    sc_core::sc_start(200, sc_core::SC_NS);
    std::cout << "[CYCLE: 20] [SYSTEM] Example 3 Finished ===\n";

    // Close trace file
    if (tf) {
        sc_core::sc_close_vcd_trace_file(tf);
        std::cout << "[SYSTEM] Waveform dumped successfully to " << vcd_name << ".vcd\n";
    }

    return 0;
}
