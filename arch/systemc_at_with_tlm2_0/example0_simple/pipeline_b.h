#ifndef PIPELINE_B_H
#define PIPELINE_B_H

// ============================================================================
// SYSTEMC & PERFORMANCE MODELING UTILITIES:
// - simple_target_socket: Sockets designed for targets (receives requests fw,
//   sends phase updates bw).
// - peq_with_get: Payload Event Queue. A crucial performance modeling utility
//   that schedules transaction events to trigger after a specific execution delay.
//   It allows simulating latencies without blocking SystemC threads.
// ============================================================================
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

// ============================================================================
// PipelineB Module
// - Acts as a target to Initiator A, and an initiator to Target C.
// - Demonstrates a 3-cycle pipelined processing unit using PEQ.
// ============================================================================
class PipelineB : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<PipelineB> target_socket;
    tlm_utils::simple_initiator_socket<PipelineB> initiator_socket;

    // VCD Tracing Signals
    // - sc_signal: SystemC signal type that tracks values over time and dumps
    //   transitions to the VCD file when registered.
    sc_core::sc_signal<int> sig_pipeline_depth;
    sc_core::sc_signal<int> sig_A_B_req_tx;
    sc_core::sc_signal<int> sig_B_C_req_tx;

    SC_HAS_PROCESS(PipelineB);
    PipelineB(sc_core::sc_module_name name) 
        : sc_core::sc_module(name), target_socket("target_socket"), initiator_socket("initiator_socket"),
          m_cycle_time(10, sc_core::SC_NS), m_peq("peq"),
          m_A_B_req_tx(0), m_B_C_req_tx(0) {
        
        // Sockets registration
        target_socket.register_nb_transport_fw(this, &PipelineB::nb_transport_fw);
        initiator_socket.register_nb_transport_bw(this, &PipelineB::nb_transport_bw);
        
        // SC_THREAD: Main processing thread representing the pipeline stage.
        SC_THREAD(pipeline_thread);
        
        // ============================================================================
        // SC_METHOD (SystemC Method Process):
        // - Unlike SC_THREADs, SC_METHODs do NOT have their own thread context and
        //   CANNOT call wait().
        // - They run as quick callbacks triggered by events on their sensitivity list.
        // - Excellent for driving VCD signals on events.
        // ============================================================================
        SC_METHOD(update_signals);
        sensitive << m_signal_event; // Runs whenever m_signal_event is notified.

        // Register clear callbacks for interface VCD signals
        SC_METHOD(clear_A_B_req);
        sensitive << m_clear_A_B_req_event;
        dont_initialize(); // dont_initialize: Prevents the method from running at startup.

        SC_METHOD(clear_B_C_req);
        sensitive << m_clear_B_C_req_event;
        dont_initialize();

        // Initial VCD signals values
        sig_pipeline_depth.write(0);
        sig_A_B_req_tx.write(0);
        sig_B_C_req_tx.write(0);
    }

    // register_trace: Binds SystemC signals to a trace file for VCD generation.
    void register_trace(sc_core::sc_trace_file* tf, const std::string& prefix) {
        sc_core::sc_trace(tf, sig_pipeline_depth, prefix + ".pipeline_depth");
        sc_core::sc_trace(tf, sig_A_B_req_tx, prefix + ".A_B_req_tx");
        sc_core::sc_trace(tf, sig_B_C_req_tx, prefix + ".B_C_req_tx");
    }

private:
    sc_core::sc_time m_cycle_time;
    tlm_utils::peq_with_get<tlm::tlm_generic_payload> m_peq; // Payload Event Queue
    std::set<tlm::tlm_generic_payload*> m_active_transactions; // Tracks active items inside the block
    
    int m_A_B_req_tx;
    int m_B_C_req_tx;

    // Events used to trigger SC_METHODs
    sc_core::sc_event m_signal_event;
    sc_core::sc_event m_clear_A_B_req_event;
    sc_core::sc_event m_clear_B_C_req_event;

    // Centralized Signal Update Method
    void update_signals() {
        sig_pipeline_depth.write(m_active_transactions.size());
        sig_A_B_req_tx.write(m_A_B_req_tx);
        sig_B_C_req_tx.write(m_B_C_req_tx);
    }

    // VCD clear methods triggered asynchronously on delay expiration
    void clear_A_B_req() {
        m_A_B_req_tx = 0;
        m_signal_event.notify();
    }

    void clear_B_C_req() {
        m_B_C_req_tx = 0;
        m_signal_event.notify();
    }

    // ============================================================================
    // nb_transport_fw (Forward path target callback)
    // - Receives transactions from Initiator A.
    // - Implements register delay and enqueues requests to PEQ.
    // ============================================================================
    tlm::tlm_sync_enum nb_transport_fw(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::BEGIN_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [PIPELINE_B] Received BEGIN_REQ for Tx " 
                      << trans.get_address() << "\n";

            int tx_id = trans.get_address() + 1; // 1-indexed transaction ID for tracing
            m_A_B_req_tx = tx_id;
            m_active_transactions.insert(&trans);
            m_signal_event.notify(delay);

            // ============================================================================
            // Scheduling PEQ Events:
            // - We notify the PEQ with a delay of (delay + 3 cycles).
            // - This schedules the payload to expire 3 cycles in the future.
            // - PEQ is non-blocking, so this function returns immediately.
            // ============================================================================
            m_peq.notify(trans, delay + 3 * m_cycle_time);

            // Schedule clearing the A-B request signal 1 cycle after arrival.
            // The request handshake occupies the interface for 1 clock cycle.
            m_clear_A_B_req_event.notify(delay + m_cycle_time);

            // Respond with END_REQ after 1 cycle of input register delay.
            phase = tlm::END_REQ;
            delay = delay + m_cycle_time;

            // TLM_UPDATED: Tells the initiator we updated the phase parameter directly.
            return tlm::TLM_UPDATED;
        }
        return tlm::TLM_ACCEPTED;
    }

    // ============================================================================
    // nb_transport_bw (Backward path initiator callback)
    // - Receives backward phase updates from Target C.
    // ============================================================================
    tlm::tlm_sync_enum nb_transport_bw(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        if (phase == tlm::END_REQ) {
            // Target C returned END_REQ, indicating it accepted the forwarded request.
            m_clear_B_C_req_event.notify(delay);
            m_active_transactions.erase(&trans);
            m_signal_event.notify(delay);
            return tlm::TLM_ACCEPTED;
        }
        return tlm::TLM_ACCEPTED;
    }

    // worker thread processing pipeline events
    void pipeline_thread() {
        while (true) {
            // Block on the PEQ's event. SystemC yields control back to the scheduler.
            wait(m_peq.get_event());

            tlm::tlm_generic_payload* trans;
            // Retrieve all payloads that have reached their expiration latency.
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

                // Handle direct updates (if C returns TLM_UPDATED immediately)
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
