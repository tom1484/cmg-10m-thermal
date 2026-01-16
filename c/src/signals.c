/*
 * Signal handling implementation.
 * Provides graceful shutdown for streaming operations.
 */

#include <stdio.h>
#include <string.h>

#include "signals.h"

/* Global running flag - volatile for signal safety */
volatile sig_atomic_t g_running = 1;

/* Signal handler for SIGINT and SIGTERM */
static void shutdown_handler(int sig) {
    (void)sig;  /* Suppress unused parameter warning */
    g_running = 0;
    /* Note: fprintf is not async-signal-safe, but this is acceptable
     * for our use case since we're shutting down anyway */
    fprintf(stderr, "\nShutting down...\n");
}

/* Install signal handlers for graceful shutdown */
void signals_install_handlers(void) {
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = shutdown_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;  /* No SA_RESTART - we want blocking calls to be interrupted */
    
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);
}
