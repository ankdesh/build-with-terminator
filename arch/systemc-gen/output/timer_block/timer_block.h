#ifndef _TIMER_BLOCK_H_
#define _TIMER_BLOCK_H_

#include <systemc>
#include <tlm>
#include "tlm_utils/simple_initiator_socket.h"
#include "tlm_utils/simple_target_socket.h"
#include "timer_block_regs.h"

class timer_block : public sc_core::sc_module {
public:
    // Sockets
    // Protocol: APB
    tlm_utils::simple_target_socket<timer_block> s_apb;
    // Protocol: AXI4
    tlm_utils::simple_initiator_socket<timer_block> m_axi;

    // Ports
    sc_core::sc_in<bool> clk;
    sc_core::sc_in<bool> rst_n;
    sc_core::sc_out<bool> irq;
    sc_core::sc_in<sc_dt::sc_bv<8>> cfg_data;

    // Register Map Instance
    timer_block_regs_t regs;

    // Constructor
    SC_HAS_PROCESS(timer_block);
    timer_block(sc_core::sc_module_name nm);

private:
    // TLM Target Socket Callbacks
    virtual void s_apb_b_transport(tlm::tlm_generic_payload& trans, sc_core::sc_time& delay);
    virtual bool s_apb_get_direct_mem_ptr(tlm::tlm_generic_payload& trans, tlm::tlm_dmi& dmi_data);
    virtual unsigned int s_apb_transport_dbg(tlm::tlm_generic_payload& trans);
};

#endif // _TIMER_BLOCK_H_