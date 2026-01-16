/*
 * Get command header.
 * Reads data from MCC 134 channels.
 */

#ifndef COMMANDS_GET_H
#define COMMANDS_GET_H

#include "common.h"

int cmd_get(int argc, char **argv);

/* ============================================================================
 * NEW API using ChannelReading and BoardInfo (Phase 3)
 * ============================================================================ */

/* Collect dynamic readings from a channel (board must be open, TC type set) */
int channel_reading_collect(ChannelReading *reading, uint8_t address, uint8_t channel,
                           int get_temp, int get_adc, int get_cjc);

/* Collect board info (board must be open) */
int board_info_collect(BoardInfo *info, uint8_t address, uint8_t channel,
                      int get_serial, int get_cal_date, int get_cal_coeffs, int get_interval);

/* Output ChannelReading as JSON */
void channel_reading_output_json(const ChannelReading *reading, const char *key);

/* Output BoardInfo as JSON */
void board_info_output_json(const BoardInfo *info, uint8_t channel);

/* ============================================================================
 * LEGACY API using ThermoData (maintained for backward compatibility)
 * ============================================================================ */

void thermo_data_init(ThermoData *data, int address, int channel);
int thermo_data_collect(ThermoData *data, int get_serial, int get_cal_date, 
                        int get_cal_coeffs, int get_temp, int get_adc, 
                        int get_cjc, int get_interval, const ThermalSource *source);
void thermo_data_output_json(const ThermoData *data, int include_address_channel);
void thermo_data_output_table(const ThermoData *data, int show_header, int clean_mode);
void thermo_data_split(const ThermoData *data, ThermoData *static_data, ThermoData *dynamic_data);

#endif /* COMMANDS_GET_H */
