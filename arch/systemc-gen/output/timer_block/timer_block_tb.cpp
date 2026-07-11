#include <systemc>
#include <tlm>
#include "timer_block.h"
#include <iostream>
#include <cassert>

// Dummy Initiator module to send test transactions
class DummyInitiator : public sc_core::sc_module {
public:
    tlm_utils::simple_initiator_socket<DummyInitiator> socket;

    SC_CTOR(DummyInitiator) : socket("socket") {
        SC_THREAD(run);
    }

    void run() {
        sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
        
        // Test 1: Write to the first register
        uint32_t write_val = 0xA5A5;
        tlm::tlm_generic_payload trans;
        trans.set_command(tlm::TLM_WRITE_COMMAND);
        trans.set_address(0x00);
        trans.set_data_ptr(reinterpret_cast<unsigned char*>(&write_val));
        trans.set_data_length(sizeof(write_val));
        trans.set_streaming_width(sizeof(write_val));
        trans.set_byte_enable_ptr(nullptr);
        trans.set_dmi_allowed(false);
        trans.set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);

        std::cout << "TB: Writing 0x" << std::hex << write_val << " to register CONTROL at offset 0x" << 0x00 << std::endl;
        socket->b_transport(trans, delay);

        assert(trans.get_response_status() == tlm::TLM_OK_RESPONSE);

        // Test 2: Read back from the first register
        uint32_t read_val = 0;
        trans.set_command(tlm::TLM_READ_COMMAND);
        trans.set_data_ptr(reinterpret_cast<unsigned char*>(&read_val));
        trans.set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);

        std::cout << "TB: Reading from register CONTROL" << std::endl;
        socket->b_transport(trans, delay);

        assert(trans.get_response_status() == tlm::TLM_OK_RESPONSE);
        std::cout << "TB: Read value: 0x" << std::hex << read_val << std::endl;
        assert(read_val == write_val);
        std::cout << "TB: Verification SUCCESSFUL!" << std::endl;
        
        sc_core::sc_stop();
    }
};

// Dummy Target module to bind to any initiator sockets on the generated block
class DummyTarget : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<DummyTarget> socket;

    SC_CTOR(DummyTarget) : socket("socket") {
        socket.register_b_transport(this, &DummyTarget::b_transport);
    }

    void b_transport(tlm::tlm_generic_payload& trans, sc_core::sc_time& delay) {
        trans.set_response_status(tlm::TLM_OK_RESPONSE);
    }
};

int sc_main(int argc, char* argv[]) {
    // Instantiate the generated block
    timer_block top_block("top_block");

    // Bind sockets
    // Target sockets on block are bound to DummyInitiators
    DummyInitiator initiator_s_apb("initiator_s_apb");
    initiator_s_apb.socket.bind(top_block.s_apb);

    // Initiator sockets on block are bound to DummyTargets
    DummyTarget target_m_axi("target_m_axi");
    top_block.m_axi.bind(target_m_axi.socket);

    // Bind discrete ports/pins to dummy signals
    sc_core::sc_signal<bool> sig_clk("sig_clk");
    top_block.clk.bind(sig_clk);
    sc_core::sc_signal<bool> sig_rst_n("sig_rst_n");
    top_block.rst_n.bind(sig_rst_n);
    sc_core::sc_signal<bool> sig_irq("sig_irq");
    top_block.irq.bind(sig_irq);
    sc_core::sc_signal<sc_dt::sc_bv<8>> sig_cfg_data("sig_cfg_data");
    top_block.cfg_data.bind(sig_cfg_data);

    std::cout << "TB: Starting simulation..." << std::endl;
    sc_core::sc_start();
    std::cout << "TB: Simulation finished." << std::endl;

    return 0;
}