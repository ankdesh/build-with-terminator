#ifndef SWITCH_TARGET_H
#define SWITCH_TARGET_H

#include <systemc>
#include <tlm>
#include <tlm_utils/multi_passthrough_target_socket.h>
#include <tlm_utils/multi_passthrough_initiator_socket.h>
#include <tlm_utils/peq_with_get.h>
#include <queue>
#include <map>
#include <vector>
#include <iostream>

#ifndef CYC_LOG
inline int get_cycle() {
    return static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
}
#define CYC_LOG() "[CYCLE: " << get_cycle() << "] "
#endif

class SwitchTarget : public sc_core::sc_module {
public:
    tlm_utils::multi_passthrough_target_socket<SwitchTarget, 32> target_sockets;
    tlm_utils::multi_passthrough_initiator_socket<SwitchTarget, 32> initiator_sockets;

    // VCD Tracing Signals
    sc_core::sc_signal<bool> sig_switch_busy;
    sc_core::sc_signal<int> sig_switch_rr_index;
    sc_core::sc_signal<int> sig_active_initiator_id;
    sc_core::sc_signal<int> sig_pending_req_count;

    SC_HAS_PROCESS(SwitchTarget);
    SwitchTarget(sc_core::sc_module_name name) 
        : sc_core::sc_module(name), target_sockets("target_sockets"), initiator_sockets("initiator_sockets"),
          m_cycle_time(10, sc_core::SC_NS), m_rr_index(0), m_switch_busy(false), m_active_init_id(-1), m_peq("peq") {
        
        target_sockets.register_nb_transport_fw(this, &SwitchTarget::nb_transport_fw);
        initiator_sockets.register_nb_transport_bw(this, &SwitchTarget::nb_transport_bw);
        
        SC_THREAD(arbiter_thread);
        SC_THREAD(busy_release_thread);

        SC_METHOD(update_signals);
        sensitive << m_signal_event;

        // Initial VCD signals
        sig_switch_busy.write(false);
        sig_switch_rr_index.write(0);
        sig_active_initiator_id.write(0);
        sig_pending_req_count.write(0);
    }

    void register_trace(sc_core::sc_trace_file* tf, const std::string& prefix) {
        sc_core::sc_trace(tf, sig_switch_busy, prefix + ".switch_busy");
        sc_core::sc_trace(tf, sig_switch_rr_index, prefix + ".switch_rr_index");
        sc_core::sc_trace(tf, sig_active_initiator_id, prefix + ".active_initiator_id");
        sc_core::sc_trace(tf, sig_pending_req_count, prefix + ".pending_req_count");
    }

private:
    struct Request {
        int init_id;
        tlm::tlm_generic_payload* trans;
        sc_core::sc_time arrival_time;
    };

    sc_core::sc_time m_cycle_time;
    int m_rr_index;
    bool m_switch_busy;
    int m_active_init_id;

    std::vector<Request> m_pending_requests;
    std::map<tlm::tlm_generic_payload*, int> m_trans_to_init;
    tlm_utils::peq_with_get<tlm::tlm_generic_payload> m_peq; // PEQ for switch transmission locks

    sc_core::sc_event m_arbiter_event;
    sc_core::sc_event m_switch_free_event;
    sc_core::sc_event m_signal_event;

    // Centralized Signal Update Method
    void update_signals() {
        sig_switch_busy.write(m_switch_busy);
        sig_switch_rr_index.write(m_rr_index);
        sig_active_initiator_id.write(m_switch_busy ? (m_active_init_id + 1) : 0);
        sig_pending_req_count.write(m_pending_requests.size());
    }

    // FW path from Initiators
    tlm::tlm_sync_enum nb_transport_fw(int id, tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::BEGIN_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [SWITCH] Request BEGIN_REQ received from Initiator " << id 
                      << " to Target Node " << trans.get_address() << "\n";

            m_trans_to_init[&trans] = id;

            Request r = {id, &trans, sc_core::sc_time_stamp() + delay};
            m_pending_requests.push_back(r);

            m_signal_event.notify(delay);
            m_arbiter_event.notify(delay);

            return tlm::TLM_ACCEPTED;
        }
        return tlm::TLM_ACCEPTED;
    }

    // BW path from Target Nodes (Not used in pure 2-phase)
    tlm::tlm_sync_enum nb_transport_bw(int /*id*/, tlm::tlm_generic_payload& /*trans*/, tlm::tlm_phase& /*phase*/, sc_core::sc_time& /*delay*/) {
        return tlm::TLM_ACCEPTED;
    }

    void arbiter_thread() {
        while (true) {
            if (m_pending_requests.empty()) {
                wait(m_arbiter_event);
            }

            if (m_switch_busy) {
                wait(m_switch_free_event);
            }

            if (m_pending_requests.empty()) {
                continue;
            }

            // Find request using Round-Robin
            int selected_idx = -1;
            for (int i = 0; i < 4; ++i) {
                int cand_id = (m_rr_index + i) % 4;
                for (size_t j = 0; j < m_pending_requests.size(); ++j) {
                    if (m_pending_requests[j].init_id == cand_id) {
                        selected_idx = j;
                        break;
                    }
                }
                if (selected_idx != -1) break;
            }

            if (selected_idx != -1) {
                Request r = m_pending_requests[selected_idx];
                m_pending_requests.erase(m_pending_requests.begin() + selected_idx);

                m_switch_busy = true;
                m_active_init_id = r.init_id;
                
                std::cout << CYC_LOG() << "[SWITCH] Arbiter GRANTED access to Initiator " << r.init_id 
                          << " (next RR: " << (r.init_id + 1) % 4 << ")\n";

                m_signal_event.notify();

                // 1. Release initiator request phase: Send END_REQ backward
                tlm::tlm_phase phase = tlm::END_REQ;
                sc_core::sc_time delay = m_cycle_time;
                target_sockets[r.init_id]->nb_transport_bw(*r.trans, phase, delay);

                // 2. Forward BEGIN_REQ to destination target node after 1 cycle switch delay
                int dest_node = r.trans->get_address();
                phase = tlm::BEGIN_REQ;
                delay = m_cycle_time;
                
                tlm::tlm_sync_enum status = initiator_sockets[dest_node]->nb_transport_fw(*r.trans, phase, delay);
                if (status == tlm::TLM_UPDATED && phase == tlm::END_REQ) {
                    int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
                    std::cout << "[CYCLE: " << cyc << "] [SWITCH] Target node " << dest_node << " accepted request.\n";
                }

                // 3. Register busy transmission complete event with PEQ to release busy status after 3 cycles
                m_peq.notify(*r.trans, 3 * m_cycle_time);

                // Update Round Robin index
                m_rr_index = (r.init_id + 1) % 4;
                m_signal_event.notify();
            }
        }
    }

    void busy_release_thread() {
        while (true) {
            // Block on PEQ event
            wait(m_peq.get_event());

            tlm::tlm_generic_payload* trans;
            while ((trans = m_peq.get_next_transaction())) {
                m_switch_busy = false;
                m_active_init_id = -1;
                std::cout << CYC_LOG() << "[SWITCH] Switch transmission complete (freeing switch).\n";
                
                m_signal_event.notify();
                m_switch_free_event.notify();
            }
        }
    }
};

#endif
