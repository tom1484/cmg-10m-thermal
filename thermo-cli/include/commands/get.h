/*
 * Get command header.
 * Reads data from MCC 134 channels.
 */

#ifndef COMMANDS_GET_H
#define COMMANDS_GET_H

#include "common.h"

int cmd_get(int argc, char **argv);

/* ============================================================================
 * NEW API using ChannelReading and BoardInfo
 * ============================================================================ */

/* Collect dynamic readings from a channel (board must be open, TC type set) */
int channel_reading_collect(ChannelReading *reading, uint8_t address, uint8_t channel,
                           int get_temp, int get_adc, int get_cjc);

/* Collect board info (board must be open) */
int board_info_collect(BoardInfo *info, uint8_t address, uint8_t channel,
                      int get_serial, int get_cal_date, int get_cal_coeffs, int get_interval);

#endif /* COMMANDS_GET_H */
