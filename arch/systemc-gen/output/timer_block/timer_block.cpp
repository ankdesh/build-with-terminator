#include "timer_block.h"
#include <cstring>

// Constructor
timer_block::timer_block(sc_core::sc_module_name nm) : sc_core::sc_module(nm) {
    s_apb.register_b_transport(this, &timer_block::s_apb_b_transport);
    s_apb.register_get_direct_mem_ptr(this, &timer_block::s_apb_get_direct_mem_ptr);
    s_apb.register_transport_dbg(this, &timer_block::s_apb_transport_dbg);
}

/**
 * TLM-2.0 Blocking transport callback for socket: s_apb
 */
void timer_block::s_apb_b_transport(tlm::tlm_generic_payload& trans, sc_core::sc_time& delay) {
    tlm::tlm_command cmd = trans.get_command();
    uint64_t adr = trans.get_address();
    unsigned char* ptr = trans.get_data_ptr();
    unsigned int len = trans.get_data_length();
    unsigned char* byt = trans.get_byte_enable_ptr();
    unsigned int wid = trans.get_streaming_width();

    // Check byte enable and streaming width
    if (byt != nullptr || wid < len) {
        trans.set_response_status(tlm::TLM_BYTE_ENABLE_ERROR_RESPONSE);
        return;
    }

    switch (adr) {
        case 0x00: {
            if (cmd == tlm::TLM_READ_COMMAND) {
                if (len <= sizeof(regs.CONTROL.value)) {
                    std::memcpy(ptr, &regs.CONTROL.value, len);
                    trans.set_response_status(tlm::TLM_OK_RESPONSE);
                } else {
                    trans.set_response_status(tlm::TLM_BURST_ERROR_RESPONSE);
                }
            } else if (cmd == tlm::TLM_WRITE_COMMAND) {
                if (len <= sizeof(regs.CONTROL.value)) {
                    std::memcpy(&regs.CONTROL.value, ptr, len);
                    trans.set_response_status(tlm::TLM_OK_RESPONSE);
                } else {
                    trans.set_response_status(tlm::TLM_BURST_ERROR_RESPONSE);
                }
            }
            break;
        }
        case 0x04: {
            if (cmd == tlm::TLM_READ_COMMAND) {
                if (len <= sizeof(regs.STATUS.value)) {
                    std::memcpy(ptr, &regs.STATUS.value, len);
                    trans.set_response_status(tlm::TLM_OK_RESPONSE);
                } else {
                    trans.set_response_status(tlm::TLM_BURST_ERROR_RESPONSE);
                }
            } else if (cmd == tlm::TLM_WRITE_COMMAND) {
                // Write to read-only register
                trans.set_response_status(tlm::TLM_WRITE_FAILURE_RESPONSE);
            }
            break;
        }
        default:
            trans.set_response_status(tlm::TLM_ADDRESS_ERROR_RESPONSE);
            break;
    }
}

/**
 * Direct memory pointer support. Not supported for standard register block access.
 */
bool timer_block::s_apb_get_direct_mem_ptr(tlm::tlm_generic_payload& trans, tlm::tlm_dmi& dmi_data) {
    return false;
}

/**
 * Debug transport callback. Allows reading/writing registers without modifying simulated time or state.
 */
unsigned int timer_block::s_apb_transport_dbg(tlm::tlm_generic_payload& trans) {
    tlm::tlm_command cmd = trans.get_command();
    uint64_t adr = trans.get_address();
    unsigned char* ptr = trans.get_data_ptr();
    unsigned int len = trans.get_data_length();
    unsigned int bytes_copied = 0;

    switch (adr) {
        case 0x00: {
            bytes_copied = (len < sizeof(regs.CONTROL.value)) ? len : sizeof(regs.CONTROL.value);
            if (cmd == tlm::TLM_READ_COMMAND) {
                std::memcpy(ptr, &regs.CONTROL.value, bytes_copied);
            } else if (cmd == tlm::TLM_WRITE_COMMAND) {
                std::memcpy(&regs.CONTROL.value, ptr, bytes_copied);
            }
            break;
        }
        case 0x04: {
            bytes_copied = (len < sizeof(regs.STATUS.value)) ? len : sizeof(regs.STATUS.value);
            if (cmd == tlm::TLM_READ_COMMAND) {
                std::memcpy(ptr, &regs.STATUS.value, bytes_copied);
            } else if (cmd == tlm::TLM_WRITE_COMMAND) {
                bytes_copied = 0;
            }
            break;
        }
        default:
            break;
    }
    return bytes_copied;
}
