#ifndef INITIATOR_A_H
#define INITIATOR_A_H

// ============================================================================
// SYSTEMC & TLM 2.0 BASIC CONCEPTS:
// - <systemc>: The core library providing hardware-like concurrency, simulation
//   time, module structures, and thread scheduling.
// - <tlm>: Transaction-Level Modeling library. TLM abstracts pin-level signals
//   (like clock, valid, data wires) into transaction function calls.
// - simple_initiator_socket: A convenience socket class used by initiators (masters)
//   to send transactions forward and receive phase updates backward.
// ============================================================================
#include <systemc>
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <iostream>
#include <vector>

// Helper macro to print cycle-accurate simulator logs.
// - sc_time_stamp(): Returns the current simulation time as a SystemC sc_time object.
// - In our models, 1 clock cycle is defined as 10 ns (100 MHz clock rate).
#ifndef CYC_LOG
inline int get_cycle() {
    return static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
}
#define CYC_LOG() "[CYCLE: " << get_cycle() << "] "
#endif

// ============================================================================
// InitiatorA Module
// - In SystemC, hardware blocks are represented as modules by inheriting from
//   sc_core::sc_module.
// - InitiatorA is a traffic source. It generates transaction payloads and
//   initiates the handshake protocol.
// ============================================================================
class InitiatorA : public sc_core::sc_module {
public:
    // Sockets are the ports through which TLM transactions pass.
    // An initiator socket binds to a target socket and enables non-blocking transport.
    tlm_utils::simple_initiator_socket<InitiatorA> socket;

    // Macro required by SystemC to define constructors for modules.
    SC_HAS_PROCESS(InitiatorA);
    
    InitiatorA(sc_core::sc_module_name name, int scenario = 1) 
        : sc_core::sc_module(name), socket("socket"), m_scenario(scenario), m_req_in_progress(false) {
        
        // Register the backward callback function.
        // In Approximately-Timed (AT) models, target blocks call back to the initiator
        // asynchronously using nb_transport_bw to close phases (like returning END_REQ).
        socket.register_nb_transport_bw(this, &InitiatorA::nb_transport_bw);
        
        // SC_THREAD: A SystemC process that runs concurrently, has its own execution
        // context, and can yield execution back to the scheduler using wait().
        SC_THREAD(stimulus_thread);
    }

private:
    int m_scenario;
    bool m_req_in_progress;
    sc_core::sc_event m_end_req_event; // SystemC event used to stall/resume threads.
    
    // Memory pools to prevent memory leaks during simulation.
    std::vector<tlm::tlm_generic_payload*> m_transactions;
    std::vector<int*> m_allocated_data;

    // ============================================================================
    // nb_transport_bw (Non-blocking transport backward path)
    // - This callback is triggered when the target calls the backward path of
    //   this socket.
    // - In 2-phase AT modeling, the target calls this with phase = END_REQ to
    //   indicate that the transaction request handshake has completed.
    // ============================================================================
    tlm::tlm_sync_enum nb_transport_bw(tlm::tlm_generic_payload& trans, tlm::tlm_phase& phase, sc_core::sc_time& delay) {
        int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);

        if (phase == tlm::END_REQ) {
            std::cout << "[CYCLE: " << cyc << "] [INITIATOR_A] Received backward call for Tx " 
                      << trans.get_address() << " with phase: END_REQ\n";
            
            // Release the handshake progress lock.
            m_req_in_progress = false;
            
            // Notify the blocked thread to resume after the specified delay.
            m_end_req_event.notify(delay);
            
            // TLM_ACCEPTED: Tells the target that we accepted the phase update.
            return tlm::TLM_ACCEPTED;
        }
        return tlm::TLM_ACCEPTED;
    }

    // ============================================================================
    // send_transaction
    // - Creates a generic payload and initiates a 2-phase transport call.
    // - Under TLM 2.0 rules, an initiator MUST NOT send a new transaction on a
    //   socket if a request phase is currently in progress (m_req_in_progress = true).
    // ============================================================================
    void send_transaction(int id) {
        // TLM Generic Payload represents the transaction object.
        // It hoists common bus properties like command, address, data, and response.
        tlm::tlm_generic_payload* trans = new tlm::tlm_generic_payload();
        int* data_ptr = new int(100 + id);
        m_allocated_data.push_back(data_ptr);

        trans->set_command(tlm::TLM_WRITE_COMMAND);
        trans->set_address(id); // Using address field as a unique transaction ID for logs.
        trans->set_data_ptr(reinterpret_cast<unsigned char*>(data_ptr));
        trans->set_data_length(sizeof(int));
        trans->set_streaming_width(sizeof(int));
        trans->set_byte_enable_ptr(0);
        trans->set_dmi_allowed(false);
        trans->set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);

        m_transactions.push_back(trans);

        // AT 2-Phase Handshake starts with BEGIN_REQ.
        tlm::tlm_phase phase = tlm::BEGIN_REQ;
        
        // delay: Models timing offsets within the current cycle.
        sc_core::sc_time delay = sc_core::SC_ZERO_TIME;

        std::cout << CYC_LOG() << "[INITIATOR_A] Sending BEGIN_REQ for Tx " << id << " with value: " << *data_ptr << "\n";

        // Lock the interface socket
        m_req_in_progress = true;
        
        // non-blocking call forward: Returns immediately without blocking the thread.
        tlm::tlm_sync_enum status = socket->nb_transport_fw(*trans, phase, delay);

        // ============================================================================
        // TLM 2.0 Return Protocol:
        // - TLM_UPDATED: The target completed the phase change directly in the call.
        //   The phase parameter is updated (e.g. to END_REQ) and the delay represents
        //   when the handshake closes.
        // - TLM_ACCEPTED: The target is processing the transaction asynchronously.
        //   The initiator must block and wait for a backward callback.
        // ============================================================================
        if (status == tlm::TLM_UPDATED && phase == tlm::END_REQ) {
            int cyc = static_cast<int>((sc_core::sc_time_stamp() + delay) / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
            std::cout << "[CYCLE: " << cyc << "] [INITIATOR_A] Direct update: phase END_REQ\n";
            m_req_in_progress = false;
        }

        // If the target returned TLM_ACCEPTED, we must stall (block) our thread
        // until the target returns END_REQ backward to notify us.
        if (m_req_in_progress) {
            wait(m_end_req_event);
        }
        
        int cyc_done = static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
        std::cout << "[CYCLE: " << cyc_done << "] [INITIATOR_A] Tx " << id << " completed (accepted by B).\n\n";
    }

    // Concurrent thread simulating traffic stimulus.
    void stimulus_thread() {
        wait(10, sc_core::SC_NS); // Start traffic at cycle 1 (T = 10ns)

        if (m_scenario == 1) {
            // Scenario 1: Send a single transaction.
            std::cout << "--- Starting Scenario 1: Single Transaction ---\n";
            send_transaction(0);
        } 
        else if (m_scenario == 2) {
            // Scenario 2: Send 5 requests back-to-back, one every cycle.
            std::cout << "--- Starting Scenario 2: Back-to-Back 5 Requests ---\n";
            for (int i = 0; i < 5; ++i) {
                send_transaction(i);
                // Yield execution for 1 clock cycle (10 ns) before the next send.
                wait(10, sc_core::SC_NS); 
            }
        } 
        else {
            // Scenario 3: Send 3 requests on alternate cycles (cycles 1, 3, 5).
            std::cout << "--- Starting Scenario 3: Alternate Cycles ---\n";
            for (int i = 0; i < 3; ++i) {
                send_transaction(i);
                // Yield execution for 2 clock cycles (20 ns).
                wait(20, sc_core::SC_NS); 
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
