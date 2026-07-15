#ifndef PRODUCER_H
#define PRODUCER_H

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

class Producer : public sc_core::sc_module {
public:
    tlm_utils::simple_initiator_socket<Producer> socket;

    SC_HAS_PROCESS(Producer);
    Producer(sc_core::sc_module_name name, int scenario = 1) 
        : sc_core::sc_module(name), socket("socket"), m_scenario(scenario), m_req_in_progress(false) {
        
        socket.register_nb_transport_bw(this, &Producer::nb_transport_bw);
        SC_THREAD(producer_thread);
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
            std::cout << "[CYCLE: " << cyc << "] [PRODUCER] Received END_REQ for write transaction " 
                      << trans.get_address() << "\n";
            m_req_in_progress = false;
            m_end_req_event.notify(delay);
            return tlm::TLM_ACCEPTED;
        }
        return tlm::TLM_ACCEPTED;
    }

    void write_fifo_nonblocking(int id, int val) {
        tlm::tlm_generic_payload* trans = new tlm::tlm_generic_payload();
        int* data_ptr = new int(val);
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

        std::cout << CYC_LOG() << "[PRODUCER] Sending write BEGIN_REQ (Tx " 
                  << id << ") with value: " << val << "\n";

        m_req_in_progress = true;
        tlm::tlm_sync_enum status = socket->nb_transport_fw(*trans, phase, delay);

        if (status == tlm::TLM_UPDATED && phase == tlm::END_REQ) {
            int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
            std::cout << "[CYCLE: " << cyc << "] [PRODUCER] Direct update: phase END_REQ for Tx " << id << ".\n";
            m_req_in_progress = false;
        }

        if (m_req_in_progress) {
            std::cout << CYC_LOG() << "[PRODUCER] Stalling on Tx " << id << " due to backpressure...\n";
            wait(m_end_req_event);
            std::cout << CYC_LOG() << "[PRODUCER] Stall released for Tx " << id << ".\n";
        }
        
        int cyc_done = static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
        std::cout << "[CYCLE: " << cyc_done << "] [PRODUCER] Tx " << id << " completed.\n\n";
    }

    void producer_thread() {
        wait(10, sc_core::SC_NS); // Start at cycle 1 (T = 10ns)

        if (m_scenario == 1) {
            // Scenario 1: Fast Producer, Slow Consumer
            for (int i = 1; i <= 6; ++i) {
                write_fifo_nonblocking(i, 100 + i);
                wait(10, sc_core::SC_NS);
            }
        } 
        else if (m_scenario == 2) {
            // Scenario 2: Slow Producer, Fast Consumer
            for (int i = 1; i <= 4; ++i) {
                write_fifo_nonblocking(i, 200 + i);
                wait(60, sc_core::SC_NS);
            }
        } 
        else {
            // Scenario 3: Bursty Traffic
            std::cout << CYC_LOG() << "[PRODUCER] Starting burst write 1 (3 items)...\n";
            for (int i = 1; i <= 3; ++i) {
                write_fifo_nonblocking(i, 300 + i);
                wait(10, sc_core::SC_NS);
            }
            wait(20, sc_core::SC_NS);
            
            std::cout << CYC_LOG() << "[PRODUCER] Starting burst write 2 (3 items)...\n";
            for (int i = 4; i <= 6; ++i) {
                write_fifo_nonblocking(i, 300 + i);
                wait(10, sc_core::SC_NS);
            }
        }
    }

public:
    ~Producer() {
        for (auto* ptr : m_allocated_data) {
            delete ptr;
        }
        for (auto* trans : m_transactions) {
            delete trans;
        }
    }
};

#endif
