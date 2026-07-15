#ifndef FIFO_TARGET_H
#define FIFO_TARGET_H

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_target_socket.h>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/peq_with_get.h>
#include <queue>
#include <iostream>

#ifndef CYC_LOG
inline int get_cycle() {
    return static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
}
#define CYC_LOG() "[CYCLE: " << get_cycle() << "] "
#endif

class FifoTarget : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<FifoTarget> write_socket;
    tlm_utils::simple_initiator_socket<FifoTarget> read_socket; // Initiator socket to Consumer

    // VCD Tracing Signals
    sc_core::sc_signal<int> sig_fifo_size;
    sc_core::sc_signal<bool> sig_producer_stalled;
    sc_core::sc_signal<bool> sig_consumer_stalled;

    SC_HAS_PROCESS(FifoTarget);
    FifoTarget(sc_core::sc_module_name name, size_t capacity = 4) 
        : sc_core::sc_module(name), write_socket("write_socket"), read_socket("read_socket"), 
          m_capacity(capacity), m_cycle_time(10, sc_core::SC_NS), m_peq("peq"),
          m_consumer_busy(false), m_active_trans(nullptr) {
        
        write_socket.register_nb_transport_fw(this, &FifoTarget::nb_transport_fw_write);
        read_socket.register_nb_transport_bw(this, &FifoTarget::nb_transport_bw_read);
        
        SC_THREAD(process_peq_thread);
        SC_THREAD(push_to_consumer_thread);

        SC_METHOD(update_signals);
        sensitive << m_signal_event;

        // Initial VCD signals
        sig_fifo_size.write(0);
        sig_producer_stalled.write(false);
        sig_consumer_stalled.write(false);
    }

    void register_trace(sc_core::sc_trace_file* tf, const std::string& prefix) {
        sc_core::sc_trace(tf, sig_fifo_size, prefix + ".fifo_size");
        sc_core::sc_trace(tf, sig_producer_stalled, prefix + ".producer_stalled");
        sc_core::sc_trace(tf, sig_consumer_stalled, prefix + ".consumer_stalled");
    }

private:
    size_t m_capacity;
    sc_core::sc_time m_cycle_time;
    std::queue<int> m_fifo_data;

    std::queue<tlm::tlm_generic_payload*> m_pending_writes;
    tlm_utils::peq_with_get<tlm::tlm_generic_payload> m_peq; // PEQ for write buffer latency

    sc_core::sc_event m_consumer_trigger_event;
    sc_core::sc_event m_consumer_released_event;
    sc_core::sc_event m_signal_event;

    bool m_consumer_busy;
    tlm::tlm_generic_payload* m_active_trans;

    // Centralized Signal Update Method
    void update_signals() {
        sig_fifo_size.write(m_fifo_data.size());
        sig_producer_stalled.write(!m_pending_writes.empty());
        sig_consumer_stalled.write(m_consumer_busy);
    }

    // FW path for writes (from Producer)
    tlm::tlm_sync_enum nb_transport_fw_write(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::BEGIN_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [FIFO] Write request BEGIN_REQ received. Size: " 
                      << m_fifo_data.size() << "/" << m_capacity << "\n";

            if (m_fifo_data.size() < m_capacity && m_pending_writes.empty()) {
                // Return END_REQ after 1 cycle delay
                phase = tlm::END_REQ;
                delay = delay + m_cycle_time;

                // Notify PEQ to push to FIFO buffer after 2 cycles write latency
                m_peq.notify(trans, delay + m_cycle_time);

                return tlm::TLM_UPDATED;
            } else {
                std::cout << "[CYCLE: " << cyc << "] [FIFO] FIFO FULL! Stall write request.\n";
                m_pending_writes.push(&trans);
                m_signal_event.notify(delay);
                return tlm::TLM_ACCEPTED; 
            }
        }
        return tlm::TLM_ACCEPTED;
    }

    // BW path from Consumer
    tlm::tlm_sync_enum nb_transport_bw_read(tlm::tlm_generic_payload& /*trans*/, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::END_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [FIFO] Consumer accepted write request.\n";
            m_consumer_busy = false;
            m_active_trans = nullptr;

            // Pop item from FIFO
            if (!m_fifo_data.empty()) {
                m_fifo_data.pop();
            }

            // Release stalled Producer
            if (!m_pending_writes.empty()) {
                tlm::tlm_generic_payload* p_trans = m_pending_writes.front();
                m_pending_writes.pop();

                std::cout << CYC_LOG() << "[FIFO] [STALL RELEASE] Accepting pending write (FIFO size: " 
                          << m_fifo_data.size() << ")\n";

                // Release producer request phase backward
                tlm::tlm_phase backward_phase = tlm::END_REQ;
                sc_core::sc_time backward_delay = m_cycle_time;
                write_socket->nb_transport_bw(*p_trans, backward_phase, backward_delay);

                // Schedule write latency in PEQ (2 cycles)
                m_peq.notify(*p_trans, backward_delay + m_cycle_time);
            }

            m_signal_event.notify(delay);
            m_consumer_released_event.notify(delay);
            return tlm::TLM_ACCEPTED;
        }
        return tlm::TLM_ACCEPTED;
    }

    void process_peq_thread() {
        while (true) {
            wait(m_peq.get_event());

            tlm::tlm_generic_payload* trans;
            while ((trans = m_peq.get_next_transaction())) {
                int value = *(reinterpret_cast<int*>(trans->get_data_ptr()));
                m_fifo_data.push(value);
                
                std::cout << CYC_LOG() << "[FIFO] Pushed value: " << value 
                          << " (FIFO size: " << m_fifo_data.size() << ")\n";

                m_signal_event.notify();
                m_consumer_trigger_event.notify();
            }
        }
    }

    void push_to_consumer_thread() {
        while (true) {
            if (m_fifo_data.empty()) {
                wait(m_consumer_trigger_event);
            }
            if (m_consumer_busy) {
                wait(m_consumer_released_event);
            }
            if (m_fifo_data.empty()) {
                continue;
            }

            int val = m_fifo_data.front();
            m_consumer_busy = true;

            // Create a payload to forward to Consumer
            m_active_trans = new tlm::tlm_generic_payload();
            m_active_trans->set_command(tlm::TLM_WRITE_COMMAND);
            m_active_trans->set_address(0);
            
            // Re-use data storage
            int* data_ptr = new int(val);
            m_active_trans->set_data_ptr(reinterpret_cast<unsigned char*>(data_ptr));
            m_active_trans->set_data_length(sizeof(int));

            tlm::tlm_phase phase = tlm::BEGIN_REQ;
            sc_core::sc_time delay = sc_core::SC_ZERO_TIME;

            std::cout << CYC_LOG() << "[FIFO] Forwarding popped value " << val << " to Consumer.\n";
            m_signal_event.notify();

            tlm::tlm_sync_enum status = read_socket->nb_transport_fw(*m_active_trans, phase, delay);

            if (status == tlm::TLM_UPDATED && phase == tlm::END_REQ) {
                int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
                std::cout << "[CYCLE: " << cyc << "] [FIFO] Consumer accepted write request immediately.\n";
                m_consumer_busy = false;
                delete data_ptr;
                delete m_active_trans;
                m_active_trans = nullptr;

                m_fifo_data.pop();

                // Release stalled Producer
                if (!m_pending_writes.empty()) {
                    tlm::tlm_generic_payload* p_trans = m_pending_writes.front();
                    m_pending_writes.pop();

                    std::cout << "[CYCLE: " << cyc << "] [FIFO] [STALL RELEASE] Accepting pending write (FIFO size: " 
                              << m_fifo_data.size() << ")\n";

                    tlm::tlm_phase backward_phase = tlm::END_REQ;
                    sc_core::sc_time backward_delay = m_cycle_time;
                    write_socket->nb_transport_bw(*p_trans, backward_phase, backward_delay);

                    m_peq.notify(*p_trans, backward_delay + m_cycle_time);
                }
                m_signal_event.notify(delay);
            }
        }
    }

public:
    ~FifoTarget() {
        if (m_active_trans) {
            delete reinterpret_cast<int*>(m_active_trans->get_data_ptr());
            delete m_active_trans;
        }
    }
};

#endif
