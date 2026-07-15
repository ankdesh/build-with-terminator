#ifndef PIPELINE_B_H
#define PIPELINE_B_H

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_target_socket.h>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/peq_with_get.h>
#include <set>
#include <iostream>

#ifndef CYC_LOG
inline int get_cycle() {
    return static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
}
#define CYC_LOG() "[CYCLE: " << get_cycle() << "] "
#endif

class PipelineB : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<PipelineB> target_socket;
    tlm_utils::simple_initiator_socket<PipelineB> initiator_socket;

    // VCD Tracing Signals
    sc_core::sc_signal<int> sig_pipeline_depth;
    sc_core::sc_signal<int> sig_A_B_req_tx;
    sc_core::sc_signal<int> sig_B_C_req_tx;

    SC_HAS_PROCESS(PipelineB);
    PipelineB(sc_core::sc_module_name name) 
        : sc_core::sc_module(name), target_socket("target_socket"), initiator_socket("initiator_socket"),
          m_cycle_time(10, sc_core::SC_NS), m_peq("peq"),
          m_A_B_req_tx(0), m_B_C_req_tx(0) {
        
        target_socket.register_nb_transport_fw(this, &PipelineB::nb_transport_fw);
        initiator_socket.register_nb_transport_bw(this, &PipelineB::nb_transport_bw);
        
        SC_THREAD(pipeline_thread);
        
        SC_METHOD(update_signals);
        sensitive << m_signal_event;

        SC_METHOD(clear_A_B_req);
        sensitive << m_clear_A_B_req_event;
        dont_initialize();

        SC_METHOD(clear_B_C_req);
        sensitive << m_clear_B_C_req_event;
        dont_initialize();

        // Initial VCD signals
        sig_pipeline_depth.write(0);
        sig_A_B_req_tx.write(0);
        sig_B_C_req_tx.write(0);
    }

    void register_trace(sc_core::sc_trace_file* tf, const std::string& prefix) {
        sc_core::sc_trace(tf, sig_pipeline_depth, prefix + ".pipeline_depth");
        sc_core::sc_trace(tf, sig_A_B_req_tx, prefix + ".A_B_req_tx");
        sc_core::sc_trace(tf, sig_B_C_req_tx, prefix + ".B_C_req_tx");
    }

private:
    sc_core::sc_time m_cycle_time;
    tlm_utils::peq_with_get<tlm::tlm_generic_payload> m_peq;
    std::set<tlm::tlm_generic_payload*> m_active_transactions;
    
    int m_A_B_req_tx;
    int m_B_C_req_tx;

    sc_core::sc_event m_signal_event;
    sc_core::sc_event m_clear_A_B_req_event;
    sc_core::sc_event m_clear_B_C_req_event;

    // Centralized Signal Update Method
    void update_signals() {
        sig_pipeline_depth.write(m_active_transactions.size());
        sig_A_B_req_tx.write(m_A_B_req_tx);
        sig_B_C_req_tx.write(m_B_C_req_tx);
    }

    // Methods to clear signals on event expiration
    void clear_A_B_req() {
        m_A_B_req_tx = 0;
        m_signal_event.notify();
    }

    void clear_B_C_req() {
        m_B_C_req_tx = 0;
        m_signal_event.notify();
    }

    // FW path from Component A (Initiator)
    tlm::tlm_sync_enum nb_transport_fw(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::BEGIN_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [PIPELINE_B] Received BEGIN_REQ for Tx " 
                      << trans.get_address() << "\n";

            int tx_id = trans.get_address() + 1; // 1-indexed for tracing (0 = idle)
            m_A_B_req_tx = tx_id;
            m_active_transactions.insert(&trans);
            m_signal_event.notify(delay);

            // Enqueue payload into PEQ with 3 cycles execution delay (30ns)
            m_peq.notify(trans, delay + 3 * m_cycle_time);

            // Schedule clearing A-B request signal 1 cycle after arrival
            m_clear_A_B_req_event.notify(delay + m_cycle_time);

            // Respond with END_REQ after 1 cycle register delay
            phase = tlm::END_REQ;
            delay = delay + m_cycle_time;

            return tlm::TLM_UPDATED;
        }
        return tlm::TLM_ACCEPTED;
    }

    // BW path from Component C (Target)
    tlm::tlm_sync_enum nb_transport_bw(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        if (phase == tlm::END_REQ) {
            // C accepted the forwarded request
            m_clear_B_C_req_event.notify(delay);
            m_active_transactions.erase(&trans);
            m_signal_event.notify(delay);
            return tlm::TLM_ACCEPTED;
        }
        return tlm::TLM_ACCEPTED;
    }

    void pipeline_thread() {
        while (true) {
            // Block on PEQ event
            wait(m_peq.get_event());

            tlm::tlm_generic_payload* trans;
            while ((trans = m_peq.get_next_transaction())) {
                std::cout << CYC_LOG() << "[PIPELINE_B] Execution complete for Tx " << trans->get_address() 
                          << ", forwarding request to Component C.\n";

                int tx_id = trans->get_address() + 1;
                m_B_C_req_tx = tx_id;
                m_signal_event.notify();

                // Forward BEGIN_REQ to Component C
                tlm::tlm_phase phase = tlm::BEGIN_REQ;
                sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
                
                tlm::tlm_sync_enum status = initiator_socket->nb_transport_fw(*trans, phase, delay);

                if (status == tlm::TLM_UPDATED && phase == tlm::END_REQ) {
                    int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
                    std::cout << "[CYCLE: " << cyc << "] [PIPELINE_B] Component C accepted request with END_REQ.\n";
                    m_clear_B_C_req_event.notify(delay);
                    m_active_transactions.erase(trans);
                    m_signal_event.notify(delay);
                }
            }
        }
    }
};

#endif
