#ifndef INITIATOR_H
#define INITIATOR_H

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <iostream>
#include <vector>

#ifndef CYC_LOG
inline int get_cycle() {
    return static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
}
#define CYC_LOG() "[CYCLE: " << get_cycle() << "] "
#endif

// ============================================================================
// Initiator Module (Example 1)
// - Represents the CPU. Generates ADD and MUL transactions and sends them
//   to the ALU target.
// ============================================================================
class Initiator : public sc_core::sc_module {
public:
    tlm_utils::simple_initiator_socket<Initiator> socket;

    SC_HAS_PROCESS(Initiator);
    Initiator(sc_core::sc_module_name name, int scenario = 1) 
        : sc_core::sc_module(name), socket("socket"), m_scenario(scenario), m_req_in_progress(false) {
        
        // Register the backward path callback to handle phase updates from target
        socket.register_nb_transport_bw(this, &Initiator::nb_transport_bw);
        
        // Concurrent thread executing stimulus patterns
        SC_THREAD(stimulus_thread);
    }

private:
    int m_scenario;
    bool m_req_in_progress;
    sc_core::sc_event m_end_req_event; // Event used to stall/block CPU execution
    
    std::vector<tlm::tlm_generic_payload*> m_transactions;
    std::vector<std::vector<int>> m_data_buffers;

    // ============================================================================
    // nb_transport_bw (Non-blocking transport backward path callback)
    // - Receives phase updates from target.
    // - When target returns END_REQ, we unblock the CPU thread.
    // ============================================================================
    tlm::tlm_sync_enum nb_transport_bw(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::END_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [INITIATOR] Received backward call for Tx " 
                      << trans.get_address() << " with phase: END_REQ\n";
            
            // Release the interface lock
            m_req_in_progress = false;
            
            // Resume the stalled thread
            m_end_req_event.notify(delay);
            return tlm::TLM_ACCEPTED;
        }
        return tlm::TLM_ACCEPTED;
    }

    // ============================================================================
    // send_transaction_nonblocking
    // - Prepares and sends an ALU transaction.
    // - Checks socket lock rules.
    // ============================================================================
    void send_transaction_nonblocking(uint64_t op_type, int op_a, int op_b) {
        tlm::tlm_generic_payload* trans = new tlm::tlm_generic_payload();
        
        // Data buffer layout: [0] = Operand A, [1] = Operand B, [2] = Output Result
        m_data_buffers.push_back({op_a, op_b, 0});
        int* data = m_data_buffers.back().data();

        trans->set_command(tlm::TLM_WRITE_COMMAND);
        trans->set_address(op_type); // Using address field as operation selector: 0=ADD, 1=MUL
        trans->set_data_ptr(reinterpret_cast<unsigned char*>(data));
        trans->set_data_length(3 * sizeof(int));
        trans->set_streaming_width(3 * sizeof(int));
        trans->set_byte_enable_ptr(0);
        trans->set_dmi_allowed(false);
        trans->set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);

        m_transactions.push_back(trans);

        tlm::tlm_phase phase = tlm::BEGIN_REQ;
        sc_core::sc_time delay = sc_core::SC_ZERO_TIME;

        std::cout << CYC_LOG() << "[INITIATOR] Sending BEGIN_REQ for Tx " 
                  << op_type << " (" << (op_type == 0 ? "ADD" : "MUL") << " " << op_a << ", " << op_b << ")\n";

        // Lock socket interface
        m_req_in_progress = true;
        
        tlm::tlm_sync_enum status = socket->nb_transport_fw(*trans, phase, delay);

        // Check if handshake completed immediately (direct update)
        if (status == tlm::TLM_UPDATED && phase == tlm::END_REQ) {
            int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
            std::cout << "[CYCLE: " << cyc << "] [INITIATOR] Direct update: phase END_REQ\n";
            m_req_in_progress = false;
        }

        // If transaction accepted asynchronously, stall CPU thread until END_REQ callback arrives
        if (m_req_in_progress) {
            wait(m_end_req_event);
        }

        int cyc_done = static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
        std::cout << "[CYCLE: " << cyc_done << "] [INITIATOR] Tx " << op_type << " accepted by ALU.\n\n";
    }

    void stimulus_thread() {
        wait(10, sc_core::SC_NS); // Start traffic at cycle 1 (T = 10ns)

        if (m_scenario == 1) {
            // Scenario 1: Mixed Pipelined ALU Operations (ADD, MUL, ADD)
            std::cout << "--- Starting Scenario 1: Mixed Operations ---\n";
            send_transaction_nonblocking(0, 10, 20); // ADD (latency 3 cycles)
            wait(10, sc_core::SC_NS);

            send_transaction_nonblocking(1, 5, 6);   // MUL (latency 4 cycles)
            wait(10, sc_core::SC_NS);

            send_transaction_nonblocking(0, 30, 40); // ADD (latency 3 cycles)
            wait(80, sc_core::SC_NS);

            send_transaction_nonblocking(1, 7, 8);   // MUL (latency 4 cycles)
        } 
        else if (m_scenario == 2) {
            // Scenario 2: In-Order Retirement Block Demonstration
            // - Starts a slow MUL (takes 4 cycles).
            // - CPU then sends fast ADDs (take 1 cycle in this scenario).
            // - The ADDs complete calculation quickly but are blocked from retiring until the MUL retires.
            std::cout << "--- Starting Scenario 2: In-Order Retirement Block ---\n";
            send_transaction_nonblocking(1, 2, 3);   // MUL (takes 4 cycles)
            wait(10, sc_core::SC_NS);

            send_transaction_nonblocking(0, 100, 200); // ADD (takes 1 cycle)
            wait(10, sc_core::SC_NS);

            send_transaction_nonblocking(0, 300, 400); // ADD (takes 1 cycle)
        } 
        else {
            // Scenario 3: Back-to-back Pipelining (Continuous ADDs)
            std::cout << "--- Starting Scenario 3: Back-to-back Pipelining ---\n";
            for (int i = 0; i < 5; ++i) {
                send_transaction_nonblocking(0, i * 10, i * 20);
                wait(10, sc_core::SC_NS);
            }
        }
    }

public:
    ~Initiator() {
        for (auto* trans : m_transactions) {
            delete trans;
        }
    }
};

#endif
