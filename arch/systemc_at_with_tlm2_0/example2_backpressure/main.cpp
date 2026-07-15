#include <systemc>
#include "producer.h"
#include "consumer.h"
#include "fifo_target.h"
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

    Producer producer("producer", scenario);
    Consumer consumer("consumer", scenario);
    FifoTarget target("fifo_target", 4); // Capacity 4

    // Bind sockets
    producer.socket.bind(target.write_socket);
    target.read_socket.bind(consumer.socket); // Bind FIFO initiator to Consumer target

    // Setup VCD Waveform Tracing
    std::string vcd_name = "example2_sc" + std::to_string(scenario);
    sc_core::sc_trace_file* tf = sc_core::sc_create_vcd_trace_file(vcd_name.c_str());
    if (tf) {
        tf->set_time_unit(1, sc_core::SC_NS); // Set VCD time resolution to 1ns
        target.register_trace(tf, "top.fifo_target");
    }

    std::cout << "[CYCLE: 0] [SYSTEM] Starting Example 2: FIFO-based Backpressure (AT) - Scenario " << scenario << " ===\n";
    sc_core::sc_start(300, sc_core::SC_NS);
    std::cout << "[CYCLE: 30] [SYSTEM] Example 2 Finished ===\n";

    // Close trace file
    if (tf) {
        sc_core::sc_close_vcd_trace_file(tf);
        std::cout << "[SYSTEM] Waveform dumped successfully to " << vcd_name << ".vcd\n";
    }

    return 0;
}
