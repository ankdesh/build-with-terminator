#ifndef TARGET_C_H
#define TARGET_C_H

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_target_socket.h>
#include <tlm_utils/peq_with_get.h>
#include <iostream>

#ifndef CYC_LOG
inline int get_cycle() {
    return static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
}
#define CYC_LOG() "[CYCLE: " << get_cycle() << "] "
#endif

// ============================================================================
// TargetC Module
// - Acts as the endpoint of our processing pipeline (Data Sink).
// - Receives transactions, models a 1-cycle processing delay, performs
//   computation (doubling the value), and retires the transactions.
// ============================================================================
class TargetC : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<TargetC> socket;

    SC_HAS_PROCESS(TargetC);
    TargetC(sc_core::sc_module_name name) 
        : sc_core::sc_module(name), socket("socket"), m_cycle_time(10, sc_core::SC_NS), m_peq("peq") {
        
        // Register the forward path target callback
        socket.register_nb_transport_fw(this, &TargetC::nb_transport_fw);
        
        // SC_THREAD: Worker thread that handles actual transaction processing
        SC_THREAD(pipeline_thread);
    }

private:
    sc_core::sc_time m_cycle_time;
    tlm_utils::peq_with_get<tlm::tlm_generic_payload> m_peq; // PEQ to model endpoint computation latency

    // ============================================================================
    // nb_transport_fw (Forward path target callback)
    // - Triggered when Component B initiates a write transaction forward.
    // - Accepts request and returns END_REQ after 1 cycle of input register delay.
    // ============================================================================
    tlm::tlm_sync_enum nb_transport_fw(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::BEGIN_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [TARGET_C] Received BEGIN_REQ for Tx " 
                      << trans.get_address() << "\n";

            // Accept request and return END_REQ after 1 cycle register delay
            phase = tlm::END_REQ;
            delay = delay + m_cycle_time;

            // ============================================================================
            // Scheduling Endpoint Processing:
            // - The endpoint takes 1 cycle of calculation latency.
            // - Since the input register delay ends at (delay) cycles, we schedule the PEQ
            //   expiration 1 cycle after that (delay + 1 cycle).
            // - Total time: starts at T, accepted at T+1, calculation completes at T+2.
            // ============================================================================
            m_peq.notify(trans, delay + m_cycle_time);

            return tlm::TLM_UPDATED;
        }
        return tlm::TLM_ACCEPTED;
    }

    void pipeline_thread() {
        while (true) {
            // Block on the PEQ's event, yielding execution back to the SystemC scheduler.
            wait(m_peq.get_event());

            tlm::tlm_generic_payload* trans;
            while ((trans = m_peq.get_next_transaction())) {
                // Perform computation: read operand data and double its value.
                int* data = reinterpret_cast<int*>(trans->get_data_ptr());
                *data = *data * 2;
                
                // TLM response status: Indicates the transaction completed successfully.
                trans->set_response_status(tlm::TLM_OK_RESPONSE);

                std::cout << CYC_LOG() << "[TARGET_C] Tx " << trans->get_address() 
                          << " completed (computation retired). Result: " << *data << "\n";
            }
        }
    }
};

#endif
