#ifndef ALU_TARGET_H
#define ALU_TARGET_H

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

class AluTarget : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<AluTarget> socket;

    // VCD Tracing Signals
    sc_core::sc_signal<bool> sig_input_stage_occupied;
    sc_core::sc_signal<int> sig_pipeline_depth;
    sc_core::sc_signal<int> sig_active_op; // 0=IDLE, 1=ADD, 2=MUL, 3=MIXED
    sc_core::sc_signal<int> sig_retired_tx_id;

    SC_HAS_PROCESS(AluTarget);
    AluTarget(sc_core::sc_module_name name, int scenario = 1) 
        : sc_core::sc_module(name), socket("socket"), m_scenario(scenario), 
          m_cycle_time(10, sc_core::SC_NS), m_tx_counter(0), m_peq("peq"), m_retired_tx_id(0), m_is_reset_phase(false) {
        
        socket.register_nb_transport_fw(this, &AluTarget::nb_transport_fw);
        SC_THREAD(pipeline_thread);
        SC_THREAD(input_release_thread);

        SC_METHOD(drive_retired_signal);
        sensitive << m_write_retired_sig_event << m_reset_retired_sig_event;
        dont_initialize();

        // Initial signal values
        sig_input_stage_occupied.write(false);
        sig_pipeline_depth.write(0);
        sig_active_op.write(0);
        sig_retired_tx_id.write(0);
    }

    void register_trace(sc_core::sc_trace_file* tf, const std::string& prefix) {
        sc_core::sc_trace(tf, sig_input_stage_occupied, prefix + ".input_stage_occupied");
        sc_core::sc_trace(tf, sig_pipeline_depth, prefix + ".pipeline_depth");
        sc_core::sc_trace(tf, sig_active_op, prefix + ".active_op");
        sc_core::sc_trace(tf, sig_retired_tx_id, prefix + ".retired_tx_id");
    }

private:
    struct TxState {
        tlm::tlm_generic_payload* trans;
        uint64_t op_type;
        int tx_id;
        bool completed;
    };

    int m_scenario;
    sc_core::sc_time m_cycle_time;
    int m_tx_counter;
    std::queue<TxState> m_pipeline_queue;
    tlm_utils::peq_with_get<tlm::tlm_generic_payload> m_peq;
    
    sc_core::sc_event m_input_received_event;
    
    int m_retired_tx_id;
    bool m_is_reset_phase;
    sc_core::sc_event m_write_retired_sig_event;
    sc_core::sc_event m_reset_retired_sig_event;

    // Single-driver VCD retired signal drive method
    void drive_retired_signal() {
        if (m_is_reset_phase) {
            sig_retired_tx_id.write(0);
            m_is_reset_phase = false;
        } else {
            sig_retired_tx_id.write(m_retired_tx_id);
            m_is_reset_phase = true;
            m_reset_retired_sig_event.notify(m_cycle_time);
        }
    }

    // Forward path implementation
    tlm::tlm_sync_enum nb_transport_fw(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
        
        if (phase == tlm::BEGIN_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [TARGET] Received BEGIN_REQ for Tx " 
                      << trans.get_address() << "\n";

            uint64_t op_type = trans.get_address();
            sc_core::sc_time latency;

            if (m_scenario == 2 && op_type == 0) {
                latency = 1 * m_cycle_time; // 1 cycle ADD in Scenario 2
            } else {
                latency = (op_type == 0) ? (3 * m_cycle_time) : (4 * m_cycle_time);
            }
            
            m_tx_counter++;
            TxState state = {&trans, op_type, m_tx_counter, false};
            m_pipeline_queue.push(state);

            // Register payload with PEQ to be notified after execution latency
            m_peq.notify(trans, delay + latency);

            // Notify target threads to update input occupied status
            m_input_received_event.notify(delay);

            // Respond with END_REQ after 1 cycle to release initiator socket
            phase = tlm::END_REQ;
            delay = delay + m_cycle_time;

            return tlm::TLM_UPDATED;
        }
        return tlm::TLM_ACCEPTED;
    }

    // Target thread driving input status signal
    void input_release_thread() {
        while (true) {
            wait(m_input_received_event);
            sig_input_stage_occupied.write(true);
            wait(m_cycle_time);
            sig_input_stage_occupied.write(false);
        }
    }

    void update_active_op_signal() {
        if (m_pipeline_queue.empty()) {
            sig_active_op.write(0); // IDLE
            return;
        }
        
        bool has_add = false;
        bool has_mul = false;
        
        std::queue<TxState> temp = m_pipeline_queue;
        while (!temp.empty()) {
            if (temp.front().op_type == 0) has_add = true;
            if (temp.front().op_type == 1) has_mul = true;
            temp.pop();
        }
        
        if (has_add && has_mul) sig_active_op.write(3); // MIXED
        else if (has_add) sig_active_op.write(1);       // ADD
        else sig_active_op.write(2);                    // MUL
    }

    // Target thread processing pipeline
    void pipeline_thread() {
        while (true) {
            // Block on the PEQ's event
            wait(m_peq.get_event());

            tlm::tlm_generic_payload* expired_trans;
            
            // Gather all completed transactions
            while ((expired_trans = m_peq.get_next_transaction())) {
                std::queue<TxState> temp_q;
                while (!m_pipeline_queue.empty()) {
                    TxState s = m_pipeline_queue.front();
                    m_pipeline_queue.pop();
                    if (s.trans == expired_trans) {
                        s.completed = true;
                    }
                    temp_q.push(s);
                }
                m_pipeline_queue = temp_q;
            }

            sig_pipeline_depth.write(m_pipeline_queue.size());
            update_active_op_signal();

            // Retire completed transactions in strict arrival order
            while (!m_pipeline_queue.empty() && m_pipeline_queue.front().completed) {
                TxState head = m_pipeline_queue.front();
                
                // Perform computation
                int* data = reinterpret_cast<int*>(head.trans->get_data_ptr());
                if (head.op_type == 0) { // ADD
                    data[2] = data[0] + data[1];
                } else if (head.op_type == 1) { // MUL
                    data[2] = data[0] * data[1];
                }
                head.trans->set_response_status(tlm::TLM_OK_RESPONSE);

                std::cout << CYC_LOG() << "[TARGET] Tx " << head.op_type 
                          << " completed (computation retired). Result: " << data[2] << "\n";

                // Trigger retired ID VCD signal
                m_retired_tx_id = head.tx_id;
                m_is_reset_phase = false;
                m_write_retired_sig_event.notify();

                m_pipeline_queue.pop();
                sig_pipeline_depth.write(m_pipeline_queue.size());
                update_active_op_signal();
            }
        }
    }
};

#endif
