#ifndef _TIMER_BLOCK_REGS_H_
#define _TIMER_BLOCK_REGS_H_

#include <cstdint>

// Individual Register Structures
/**
 * Register: CONTROL
 * Offset: 0x00
 * Size: 32 bits
 * Access: read-write
 * Description: Timer Control Register
 */
struct CONTROL_t {
    union {
        struct {
            uint32_t ENABLE : 1; // Enable the timer block
            uint32_t MODE : 3; // Operating mode (0: single-shot, 1: periodic)
            uint32_t : 28; // Reserved/Padding
        } fields;
        uint32_t value;
    };

    // Reset value initialization helper
    CONTROL_t() {
        value = 0;
    }
};

/**
 * Register: STATUS
 * Offset: 0x04
 * Size: 32 bits
 * Access: read-only
 * Description: Timer Status Register
 */
struct STATUS_t {
    union {
        struct {
            uint32_t INTR : 1; // Interrupt Pending Flag
            uint32_t : 31; // Reserved/Padding
        } fields;
        uint32_t value;
    };

    // Reset value initialization helper
    STATUS_t() {
        value = 0;
    }
};


/**
 * Register Map for timer_block component.
 */
struct timer_block_regs_t {
    CONTROL_t CONTROL; // Offset: 0x00
    STATUS_t STATUS; // Offset: 0x04
};

#endif // _TIMER_BLOCK_REGS_H_