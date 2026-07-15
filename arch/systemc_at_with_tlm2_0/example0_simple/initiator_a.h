#ifndef INITIATOR_A_H
#define INITIATOR_A_H

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

class InitiatorA : public sc_core::sc_module {
public:
    tlm_utils::simple_initiator_socket<InitiatorA> socket;

    SC_HAS_PROCESS(InitiatorA);
    InitiatorA(sc_core::sc_module_name name, int scenario = 1) 
        : sc_core::sc_module(name), socket("socket"), m_scenario(scenario), m_req_in_progress(false) {
        
        socket.register_nb_transport_bw(this, &InitiatorA::nb_transport_bw);
        SC_THREAD(stimulus_thread);
    }

private:
    int m_scenario;
    bool m_req_in_progress;
    sc_core::sc_event m_end_req_event;
    
    std::vector<tlm::tlm_generic_payload*> m_transactions;
    std::vector<int*> m_allocated_data;

    tlm::tlm_sync_enum nb_transport_bw(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::END_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [INITIATOR_A] Received backward call for Tx " 
                      << trans.get_address() << " with phase: END_REQ\n";
            m_req_in_progress = false;
            m_end_req_event.notify(delay);
            return tlm::TLM_ACCEPTED;
        }
        return tlm::TLM_ACCEPTED;
    }

    void send_transaction(int id) {
        tlm::tlm_generic_payload* trans = new tlm::tlm_generic_payload();
        int* data_ptr = new int(100 + id);
        m_allocated_data.push_back(data_ptr);

        trans->set_command(tlm::TLM_WRITE_COMMAND);
        trans->set_address(id); // Use address field as transaction ID for tracing
        trans->set_data_ptr(reinterpret_cast<unsigned char*>(data_ptr));
        trans->set_data_length(sizeof(int));
        trans->set_streaming_width(sizeof(int));
        trans->set_byte_enable_ptr(0);
        trans->set_dmi_allowed(false);
        trans->set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);

        m_transactions.push_back(trans);

        tlm::tlm_phase phase = tlm::BEGIN_REQ;
        sc_core::sc_time delay = sc_core::SC_ZERO_TIME;

        std::cout << CYC_LOG() << "[INITIATOR_A] Sending BEGIN_REQ for Tx " << id << " with value: " << *data_ptr << "\n";

        m_req_in_progress = true;
        tlm::tlm_sync_enum status = socket->nb_transport_fw(*trans, phase, delay);

        if (status == tlm::TLM_UPDATED && phase == tlm::END_REQ) {
            int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
            std::cout << "[CYCLE: " << cyc << "] [INITIATOR_A] Direct update: phase END_REQ\n";
            m_req_in_progress = false;
        }

        if (m_req_in_progress) {
            wait(m_end_req_event);
        }
        
        int cyc_done = static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
        std::cout << "[CYCLE: " << cyc_done << "] [INITIATOR_A] Tx " << id << " completed (accepted by B).\n\n";
    }

    void stimulus_thread() {
        wait(10, sc_core::SC_NS); // Start at cycle 1 (T = 10ns)

        if (m_scenario == 1) {
            // Scenario 1: Only 1 input available at cycle 1 (T=10ns)
            std::cout << "--- Starting Scenario 1: Single Transaction ---\n";
            send_transaction(0);
        } 
        else if (m_scenario == 2) {
            // Scenario 2: Back-to-back 5 requests, one each cycle
            std::cout << "--- Starting Scenario 2: Back-to-Back 5 Requests ---\n";
            for (int i = 0; i < 5; ++i) {
                send_transaction(i);
                wait(10, sc_core::SC_NS); // Wait 1 cycle before sending next
            }
        } 
        else {
            // Scenario 3: Generate 3 requests every alternate cycle
            std::cout << "--- Starting Scenario 3: Alternate Cycles ---\n";
            for (int i = 0; i < 3; ++i) {
                send_transaction(i);
                wait(20, sc_core::SC_NS); // Wait 2 cycles (alternate cycles)
            }
        }
    }

public:
    ~InitiatorA() {
        for (auto* ptr : m_allocated_data) {
            delete ptr;
        }
        for (auto* trans : m_transactions) {
            delete trans;
        }
    }
};

#endif
