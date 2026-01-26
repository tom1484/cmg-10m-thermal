/*
 * Signal handling for graceful shutdown.
 * Provides clean termination of streaming operations.
 */

#ifndef SIGNALS_H
#define SIGNALS_H

#include <signal.h>

/* Global flag for graceful shutdown */
extern volatile sig_atomic_t g_running;

/* Install signal handlers for graceful shutdown (SIGINT, SIGTERM) */
void signals_install_handlers(void);

/* Check if shutdown was requested */
static inline int signals_should_stop(void) {
    return !g_running;
}

/* Reset the running flag (for reuse in tests or multiple operations) */
static inline void signals_reset(void) {
    g_running = 1;
}

#endif /* SIGNALS_H */
