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
// Initiator Module (Example 3)
// - Represents one of 4 competing IP blocks.
// - Demonstrates switch arbitration contention: blocks on END_REQ backward
//   calls if the switch is busy or granting access to another client.
// ============================================================================
class Initiator : public sc_core::sc_module {
public:
    tlm_utils::simple_initiator_socket<Initiator> socket;
    int m_id; // Unique identifier for this client (0 to 3)

    SC_HAS_PROCESS(Initiator);
    Initiator(sc_core::sc_module_name name, int id, int scenario = 1) 
        : sc_core::sc_module(name), socket("socket"), m_id(id), m_scenario(scenario), m_req_in_progress(false) {
        
        // Register the backward path callback
        socket.register_nb_transport_bw(this, &Initiator::nb_transport_bw);
        SC_THREAD(stimulus_thread);
    }

private:
    int m_scenario;
    bool m_req_in_progress;
    sc_core::sc_event m_end_req_event; // Event used to stall/unblock this client
    
    std::vector<tlm::tlm_generic_payload*> m_transactions;
    std::vector<int*> m_allocated_data;

    // ============================================================================
    // nb_transport_bw (Non-blocking transport backward path callback)
    // - Receives phase updates from the Switch Target.
    // - When the switch arbiter grants access to this client, it sends END_REQ
    //   backward, unblocking our thread.
    // ============================================================================
    tlm::tlm_sync_enum nb_transport_bw(tlm::tlm_generic_payload& /*trans*/, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::END_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [INITIATOR_" << m_id 
                      << "] Received END_REQ (arbitration grant, switch busy phase starts).\n";
            
            // Release interface lock
            m_req_in_progress = false;
            
            // Resume our stalled sender thread
            m_end_req_event.notify(delay);
            return tlm::TLM_ACCEPTED;
        }
        return tlm::TLM_ACCEPTED;
    }

    // Sends write requests directed to target nodes
    void send_transaction(uint64_t target_address) {
        tlm::tlm_generic_payload* trans = new tlm::tlm_generic_payload();
        int* data_ptr = new int(m_id);
        m_allocated_data.push_back(data_ptr);

        trans->set_command(tlm::TLM_WRITE_COMMAND);
        trans->set_address(target_address); // Address acts as destination Node ID
        trans->set_data_ptr(reinterpret_cast<unsigned char*>(data_ptr));
        trans->set_data_length(sizeof(int));
        trans->set_streaming_width(sizeof(int));
        trans->set_byte_enable_ptr(0);
        trans->set_dmi_allowed(false);
        trans->set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);

        m_transactions.push_back(trans);

        tlm::tlm_phase phase = tlm::BEGIN_REQ;
        sc_core::sc_time delay = sc_core::SC_ZERO_TIME;

        std::cout << CYC_LOG() << "[INITIATOR_" << m_id 
                  << "] Sending BEGIN_REQ to target " << target_address << ".\n";

        // Lock socket interface
        m_req_in_progress = true;
        tlm::tlm_sync_enum status = socket->nb_transport_fw(*trans, phase, delay);

        // Check if Switch granted access immediately
        if (status == tlm::TLM_UPDATED && phase == tlm::END_REQ) {
            int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
            std::cout << "[CYCLE: " << cyc << "] [INITIATOR_" << m_id 
                      << "] Direct grant (END_REQ received immediately).\n";
            m_req_in_progress = false;
        }

        // If Switch returns TLM_ACCEPTED (switch is busy or arbiter grants another client first), stall this thread
        if (m_req_in_progress) {
            wait(m_end_req_event);
        }

        std::cout << CYC_LOG() << "[INITIATOR_" << m_id 
                  << "] Finished transaction to target " << target_address << " (arbitration grant completed).\n\n";
    }

    void stimulus_thread() {
        if (m_scenario == 1) {
            // Scenario 1: Coordinated Contention
            // All 4 initiators send requests at the exact same cycle (cycle 1), causing contention.
            wait(10, sc_core::SC_NS);
            send_transaction(m_id);
        } 
        else if (m_scenario == 2) {
            // Scenario 2: Staggered No-Contention
            // Initiators send requests at staggered cycles, avoiding switch contention entirely.
            wait(10 + m_id * 40, sc_core::SC_NS);
            send_transaction(m_id);
        } 
        else {
            // Scenario 3: Unbalanced Traffic
            // Initiator 0 floods the switch, while others make sparse requests.
            if (m_id == 0) {
                wait(10, sc_core::SC_NS);
                for (int i = 0; i < 4; ++i) {
                    send_transaction(0);
                    wait(40, sc_core::SC_NS);
                }
            } 
            else if (m_id == 1) {
                wait(10, sc_core::SC_NS);
                send_transaction(1);
            } 
            else if (m_id == 2) {
                wait(55, sc_core::SC_NS);
                send_transaction(2);
            } 
            else if (m_id == 3) {
                wait(105, sc_core::SC_NS);
                send_transaction(3);
            }
        }
    }

public:
    ~Initiator() {
        for (auto* ptr : m_allocated_data) {
            delete ptr;
        }
        for (auto* trans : m_transactions) {
            delete trans;
        }
    }
};

#endif
