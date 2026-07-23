#ifndef CONSUMER_H
#define CONSUMER_H

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_target_socket.h>
#include <tlm_utils/peq_with_get.h>
#include <queue>
#include <iostream>

#ifndef CYC_LOG
inline int get_cycle() {
    return static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
}
#define CYC_LOG() "[CYCLE: " << get_cycle() << "] "
#endif

// ============================================================================
// Consumer Module (Example 2)
// - Target block in a streaming push model.
// - Demonstrates busy-stalling: it holds the request phase (returns TLM_ACCEPTED
//   without END_REQ) when it is busy processing a transaction, causing the
//   FIFO interconnect to stall.
// ============================================================================
class Consumer : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<Consumer> socket;

    SC_HAS_PROCESS(Consumer);
    Consumer(sc_core::sc_module_name name, int scenario = 1) 
        : sc_core::sc_module(name), socket("socket"), m_scenario(scenario), 
          m_cycle_time(10, sc_core::SC_NS), m_peq("peq"), m_busy(false) {
        
        socket.register_nb_transport_fw(this, &Consumer::nb_transport_fw);
        
        SC_THREAD(consumer_thread);
        SC_THREAD(start_delayed_processing_thread);
    }

private:
    int m_scenario;
    sc_core::sc_time m_cycle_time;
    tlm_utils::peq_with_get<tlm::tlm_generic_payload> m_peq; // PEQ to model consumer calculation latency
    bool m_busy;
    std::queue<tlm::tlm_generic_payload*> m_blocked_writes; // Queue for requests stalled due to consumer busy status
    
    sc_core::sc_event m_resp_done;
    bool m_initially_disabled;

    // Controls consumer startup delays to demonstrate buffer backpressure
    void start_delayed_processing_thread() {
        m_initially_disabled = false;
        if (m_scenario == 1) {
            // Slow Consumer stays completely idle/disabled for the first 10 cycles (100ns)
            m_initially_disabled = true;
            wait(100, sc_core::SC_NS);
            m_initially_disabled = false;
            std::cout << CYC_LOG() << "[CONSUMER] Starting slow consumer processing (draining FIFO)...\n\n";
            trigger_blocked_requests();
        } else if (m_scenario == 3) {
            // Bursty Consumer stays idle/disabled for the first 4 cycles (40ns)
            m_initially_disabled = true;
            wait(40, sc_core::SC_NS);
            m_initially_disabled = false;
            std::cout << CYC_LOG() << "[CONSUMER] Starting consumer processing (draining FIFO)...\n\n";
            trigger_blocked_requests();
        }
    }

    // Helper method to release stalled FIFO write requests once the consumer completes work
    void trigger_blocked_requests() {
        if (!m_blocked_writes.empty() && !m_busy) {
            tlm::tlm_generic_payload* trans = m_blocked_writes.front();
            m_blocked_writes.pop();
            
            m_busy = true;
            int latency_cyc = (m_scenario == 1) ? 2 : 1; // Slow Consumer: 2 cycles latency, Fast/Bursty: 1 cycle

            // Release FIFO request phase backward
            tlm::tlm_phase phase = tlm::END_REQ;
            sc_core::sc_time delay = m_cycle_time;
            socket->nb_transport_bw(*trans, phase, delay);

            // Register payload with PEQ for execution delay
            m_peq.notify(*trans, delay + latency_cyc * m_cycle_time);
        }
    }

    // ============================================================================
    // nb_transport_fw (Forward path target callback)
    // - Receives data push transactions from the FIFO interconnect.
    // ============================================================================
    tlm::tlm_sync_enum nb_transport_fw(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::BEGIN_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [CONSUMER] Received write BEGIN_REQ from FIFO.\n";

            // If the consumer is temporarily disabled or busy processing, stall the request
            if (m_initially_disabled || m_busy) {
                std::cout << "[CYCLE: " << cyc << "] [CONSUMER] Consumer Busy! Stall write request.\n";
                m_blocked_writes.push(&trans);
                
                // Return TLM_ACCEPTED without updating phase to END_REQ to stall the FIFO interconnect
                return tlm::TLM_ACCEPTED;
            } else {
                m_busy = true;
                int latency_cyc = (m_scenario == 1) ? 2 : 1; // Slow: 2 cycles, Fast/Bursty: 1 cycle

                // Accept request and return END_REQ after 1 cycle register delay
                phase = tlm::END_REQ;
                delay = delay + m_cycle_time;

                m_peq.notify(trans, delay + latency_cyc * m_cycle_time);

                return tlm::TLM_UPDATED;
            }
        }
        return tlm::TLM_ACCEPTED;
    }

    void consumer_thread() {
        while (true) {
            // Block on the PEQ's event, yielding context
            wait(m_peq.get_event());

            tlm::tlm_generic_payload* trans;
            while ((trans = m_peq.get_next_transaction())) {
                int value = *(reinterpret_cast<int*>(trans->get_data_ptr()));
                std::cout << CYC_LOG() << "[CONSUMER] Completed processing value: " << value << "\n\n";

                // Free busy status and trigger arbiter release for queued items
                m_busy = false;
                trigger_blocked_requests();
            }
        }
    }
};

#endif
