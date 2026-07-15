#ifndef TARGET_NODE_H
#define TARGET_NODE_H

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_target_socket.h>
#include <tlm_utils/peq_with_get.h>
#include <iostream>

#ifndef CYC_LOG
inline int get_cycle() {
    return static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
}
#define CYC_LOG() "[CYCLE: " << get_cycle() << "] "
#endif

class TargetNode : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<TargetNode> socket;
    int m_id;

    SC_HAS_PROCESS(TargetNode);
    TargetNode(sc_core::sc_module_name name, int id) 
        : sc_core::sc_module(name), socket("socket"), m_id(id), m_cycle_time(10, sc_core::SC_NS), m_peq("peq") {
        socket.register_nb_transport_fw(this, &TargetNode::nb_transport_fw);
        SC_THREAD(pipeline_thread);
    }

private:
    sc_core::sc_time m_cycle_time;
    tlm_utils::peq_with_get<tlm::tlm_generic_payload> m_peq;

    tlm::tlm_sync_enum nb_transport_fw(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::BEGIN_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [TARGET_" << m_id << "] Received BEGIN_REQ.\n";

            // Accept request and return END_REQ after 1 cycle register delay
            phase = tlm::END_REQ;
            delay = delay + m_cycle_time;

            // Notify PEQ to model 1 cycle endpoint processing delay (T + 2 cycles total)
            m_peq.notify(trans, delay + m_cycle_time);

            return tlm::TLM_UPDATED;
        }
        return tlm::TLM_ACCEPTED;
    }

    void pipeline_thread() {
        while (true) {
            // Block on PEQ event
            wait(m_peq.get_event());

            tlm::tlm_generic_payload* trans;
            while ((trans = m_peq.get_next_transaction())) {
                int* data = reinterpret_cast<int*>(trans->get_data_ptr());
                trans->set_response_status(tlm::TLM_OK_RESPONSE);

                std::cout << CYC_LOG() << "[TARGET_" << m_id << "] Transaction completed. Result value: " 
                          << *data << "\n";
            }
        }
    }
};

#endif
