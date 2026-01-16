# Thermo-CLI Improvement Plan

This document outlines a phased approach to improving the thermo-cli codebase.

## Overview

| Phase | Description | Effort | Risk | Dependencies |
|-------|-------------|--------|------|--------------|
| **Phase 1** | Quick Fixes | 2-3 hours | Low | None |
| **Phase 2** | Signal Handling & Graceful Shutdown | 1-2 hours | Low | None |
| **Phase 3** | Data Structure Refactoring | 3-4 hours | Medium | Phase 1 |
| **Phase 4** | Board Manager Module | 2-3 hours | Medium | Phase 1, 3 |
| **Phase 5** | JSON Output Consolidation | 2-3 hours | Low | Phase 3 |
| **Phase 6** | Build System Improvements | 1 hour | Low | None |
| **Phase 7** | Testing & Documentation | 3-4 hours | Low | Phase 4 |

**Recommended order:** Phase 1 → Phase 6 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 7

---

## Phase 1: Quick Fixes (Low Risk, High Impact)

### 1.1 Fix typos in constant names

**Files:** `include/common.h`, and all files using these constants

```c
// Before
#define DAFAULT_CALIBRATION_SLOPE 0.999560
#define DAFAULT_CALIBRATION_OFFSET -38.955465
#define DAFAULT_UPDATE_INTERVAL 1

// After
#define DEFAULT_CALIBRATION_SLOPE 0.999560
#define DEFAULT_CALIBRATION_OFFSET -38.955465
#define DEFAULT_UPDATE_INTERVAL 1
```

**Affected files to update:**
- `include/common.h` (definitions)
- `src/commands/get.c` (6 occurrences)
- `src/common.c` (6 occurrences)
- `src/bridge.c` (4 occurrences)

---

### 1.2 Fix memory leaks in `output_channels_table()`

**File:** `src/commands/get.c`

The `static_data_array` and `dynamic_data_array` are allocated but never freed.

```c
// Add before the function's closing brace (around line 437)
free(static_data_array);
free(dynamic_data_array);
```

---

### 1.3 Fix `set` command opening board twice

**File:** `src/commands/set.c`

Currently opens the board separately for calibration and interval settings. Restructure to open once:

```c
int cmd_set(int argc, char **argv) {
    // ... parse options ...
    
    int need_board = (has_slope && has_offset) || has_interval;
    
    if (need_board) {
        if (thermo_open(address) != THERMO_SUCCESS) {
            fprintf(stderr, "Error opening board at address %d\n", address);
            return 1;
        }
    }
    
    int result = 0;
    
    if (has_slope && has_offset) {
        result = thermo_set_calibration_coeffs(address, channel, cal_slope, cal_offset);
        if (result == THERMO_SUCCESS) {
            printf("Calibration Coefficients (Addr %d Ch %d) set to:\n", address, channel);
            printf("  Slope:  %.6f\n", cal_slope);
            printf("  Offset: %.6f\n", cal_offset);
        } else {
            fprintf(stderr, "Error setting calibration coefficients\n");
        }
    }
    
    if (has_interval && result == THERMO_SUCCESS) {
        result = thermo_set_update_interval(address, update_interval);
        if (result == THERMO_SUCCESS) {
            printf("Update Interval (Addr %d) set to: %d seconds\n", address, update_interval);
        } else {
            fprintf(stderr, "Error setting update interval\n");
        }
    }
    
    if (need_board) {
        thermo_close(address);
    }
    
    return (result == THERMO_SUCCESS) ? 0 : 1;
}
```

---

### 1.4 Add input validation

**Files:** `src/commands/get.c`, `src/commands/set.c`, `src/bridge.c`

Create validation helpers in `include/utils.h`:

```c
/* Input validation helpers */
static inline int validate_address(int address) {
    return (address >= 0 && address <= 7);
}

static inline int validate_channel(int channel) {
    return (channel >= 0 && channel <= 3);
}
```

Add validation after argument parsing in each command:

```c
if (!validate_address(address)) {
    fprintf(stderr, "Error: Address must be 0-7\n");
    return 1;
}
if (!validate_channel(channel)) {
    fprintf(stderr, "Error: Channel must be 0-3\n");
    return 1;
}
```

---

### 1.5 Check `fread()` return value

**File:** `src/common.c`

```c
// Before
fread(content, 1, fsize, fp);

// After
size_t bytes_read = fread(content, 1, fsize, fp);
if (bytes_read != (size_t)fsize) {
    fprintf(stderr, "Error: Could not read entire config file\n");
    free(content);
    fclose(fp);
    return THERMO_IO_ERROR;
}
```

---

## Phase 2: Signal Handling & Graceful Shutdown

### 2.1 Create signal handler module

**New files:** `include/signals.h`, `src/signals.c`

```c
// include/signals.h
#ifndef SIGNALS_H
#define SIGNALS_H

#include <signal.h>

/* Global flag for graceful shutdown */
extern volatile sig_atomic_t g_running;

/* Install signal handlers for graceful shutdown */
void signals_install_handlers(void);

/* Check if shutdown was requested */
static inline int signals_should_stop(void) {
    return !g_running;
}

#endif /* SIGNALS_H */
```

```c
// src/signals.c
#include "signals.h"
#include <stdio.h>

volatile sig_atomic_t g_running = 1;

static void sigint_handler(int sig) {
    (void)sig;
    g_running = 0;
    fprintf(stderr, "\nShutting down...\n");
}

void signals_install_handlers(void) {
    struct sigaction sa;
    sa.sa_handler = sigint_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);
}
```

---

### 2.2 Update streaming functions

**File:** `src/commands/get.c`

```c
#include "signals.h"

static int stream_channels(...) {
    signals_install_handlers();
    
    // ... setup code ...
    
    while (g_running) {  // Changed from while(1)
        // ... streaming logic ...
    }
    
    close_boards(sources, source_count);  // Now this gets called!
    return 0;
}
```

---

### 2.3 Update bridge streaming

**File:** `src/bridge.c`

Similar changes to handle SIGINT gracefully in the parent process.

---

### 2.4 Update Makefile

Add `src/signals.c` to SOURCES.

---

## Phase 3: Data Structure Refactoring

### 3.1 Redesign data structures

**File:** `include/common.h`

**Note:** Calibration date and coefficients are per-channel data, so they must be stored per-channel.

```c
/* Per-channel calibration and configuration */
typedef struct {
    char cal_date[16];           /* Calibration date for this channel */
    CalibrationInfo cal_coeffs;   /* Slope and offset */
    uint8_t tc_type;              /* Thermocouple type */
} ChannelConfig;

/* Per-board static information */
typedef struct {
    uint8_t address;
    char serial[16];
    uint8_t update_interval;
    ChannelConfig channels[4];    /* Per-channel data (4 channels per MCC 134) */
} BoardInfo;

/* Dynamic reading from a single channel */
typedef struct {
    uint8_t address;
    uint8_t channel;
    double temperature;
    double adc_voltage;
    double cjc_temp;
    
    /* Availability flags (use bitfields for compact storage) */
    unsigned has_temp : 1;
    unsigned has_adc : 1;
    unsigned has_cjc : 1;
} ChannelReading;

/* Combined data for backward compatibility during transition */
typedef struct {
    BoardInfo *board_info;        /* Optional, may be NULL */
    ChannelReading reading;
    
    /* Legacy flags for gradual migration */
    unsigned has_board_info : 1;
} ThermoData;
```

---

### 3.2 Keep ThermalSource unchanged

`ThermalSource` represents user configuration (from CLI args or config file) and is distinct from hardware state:

```c
typedef struct {
    char key[64];                 /* User-defined key name */
    uint8_t address;
    uint8_t channel;
    char tc_type[8];              /* String representation */
    CalibrationInfo cal_coeffs;
    int update_interval;
} ThermalSource;
```

---

### 3.3 Migration strategy

1. Add new structures alongside existing ones
2. Create adapter functions to convert between old and new formats
3. Gradually update functions to use new structures
4. Remove old structures once migration is complete

---

## Phase 4: Board Manager Module

### 4.1 Create board manager

**New files:** `include/board_manager.h`, `src/board_manager.c`

```c
// include/board_manager.h
#ifndef BOARD_MANAGER_H
#define BOARD_MANAGER_H

#include "common.h"
#include "hardware.h"

#define MAX_BOARDS 8

typedef struct {
    uint8_t opened[MAX_BOARDS];   /* Track which boards are open */
    ThermalSource *sources;
    int source_count;
} BoardManager;

/* Initialize manager and open all required boards */
int board_manager_init(BoardManager *mgr, ThermalSource *sources, int count);

/* Apply calibration and TC type settings for all sources */
int board_manager_configure(BoardManager *mgr);

/* Close all open boards */
void board_manager_close(BoardManager *mgr);

/* Check if a specific board is open */
int board_manager_is_open(BoardManager *mgr, uint8_t address);

#endif /* BOARD_MANAGER_H */
```

```c
// src/board_manager.c
#include "board_manager.h"
#include "utils.h"
#include <string.h>
#include <stdio.h>

int board_manager_init(BoardManager *mgr, ThermalSource *sources, int count) {
    memset(mgr->opened, 0, sizeof(mgr->opened));
    mgr->sources = sources;
    mgr->source_count = count;
    
    /* Open all unique boards */
    for (int i = 0; i < count; i++) {
        uint8_t addr = sources[i].address;
        if (!mgr->opened[addr]) {
            DEBUG_PRINT("Opening board at address %d", addr);
            if (thermo_open(addr) != THERMO_SUCCESS) {
                fprintf(stderr, "Error: Failed to open board at address %d\n", addr);
                board_manager_close(mgr);
                return THERMO_ERROR;
            }
            mgr->opened[addr] = 1;
            
            /* Apply update interval */
            if (sources[i].update_interval > 0 && 
                sources[i].update_interval != DEFAULT_UPDATE_INTERVAL) {
                DEBUG_PRINT("Setting update interval for address %d to %d", 
                           addr, sources[i].update_interval);
                thermo_set_update_interval(addr, (uint8_t)sources[i].update_interval);
            }
        }
    }
    
    return THERMO_SUCCESS;
}

int board_manager_configure(BoardManager *mgr) {
    for (int i = 0; i < mgr->source_count; i++) {
        ThermalSource *src = &mgr->sources[i];
        
        /* Apply calibration coefficients if non-default */
        if (src->cal_coeffs.slope != DEFAULT_CALIBRATION_SLOPE ||
            src->cal_coeffs.offset != DEFAULT_CALIBRATION_OFFSET) {
            DEBUG_PRINT("Setting calibration for addr %d ch %d: slope=%.6f, offset=%.6f",
                       src->address, src->channel, 
                       src->cal_coeffs.slope, src->cal_coeffs.offset);
            thermo_set_calibration_coeffs(src->address, src->channel,
                                         src->cal_coeffs.slope,
                                         src->cal_coeffs.offset);
        }
        
        /* Set TC type */
        thermo_set_tc_type(src->address, src->channel, src->tc_type);
    }
    
    return THERMO_SUCCESS;
}

void board_manager_close(BoardManager *mgr) {
    for (int i = 0; i < MAX_BOARDS; i++) {
        if (mgr->opened[i]) {
            DEBUG_PRINT("Closing board at address %d", i);
            thermo_close(i);
            mgr->opened[i] = 0;
        }
    }
}

int board_manager_is_open(BoardManager *mgr, uint8_t address) {
    if (address >= MAX_BOARDS) return 0;
    return mgr->opened[address];
}
```

---

### 4.2 Refactor commands to use BoardManager

**File:** `src/commands/get.c`

Replace duplicated board management code in `collect_channels()` and `stream_channels()`:

```c
#include "board_manager.h"

static int collect_channels(ThermalSource *sources, int source_count, ThermoData **data_out,
                           int get_serial, int get_cal_date, int get_cal_coeffs,
                           int get_temp, int get_adc, int get_cjc, int get_interval) {
    BoardManager mgr;
    
    if (board_manager_init(&mgr, sources, source_count) != THERMO_SUCCESS) {
        return THERMO_ERROR;
    }
    
    if (get_temp || get_adc) {
        board_manager_configure(&mgr);
    }
    
    // ... allocate and collect data ...
    
    // Note: Don't close boards here if caller needs them open
    // Or close and let caller re-open as needed
    
    return THERMO_SUCCESS;
}
```

**File:** `src/bridge.c`

Replace `bridge_init_boards()` with BoardManager usage.

---

## Phase 5: JSON Output Consolidation

### 5.1 Create JSON builder helpers

**New file:** `src/json_utils.c` and `include/json_utils.h`

```c
// include/json_utils.h
#ifndef JSON_UTILS_H
#define JSON_UTILS_H

#include "common.h"
#include "cJSON.h"

/* Convert ChannelReading to cJSON object */
cJSON* reading_to_json(const ChannelReading *reading);

/* Add reading fields to existing cJSON object */
void reading_add_to_json(cJSON *obj, const ChannelReading *reading);

/* Convert BoardInfo to cJSON object */
cJSON* board_info_to_json(const BoardInfo *info, int channel);

/* Convert ThermoData to cJSON object (legacy compatibility) */
cJSON* thermo_data_to_json(const ThermoData *data, int include_address);

/* Convert array of readings to cJSON array */
cJSON* readings_to_json_array(const ChannelReading *readings, int count,
                              const ThermalSource *sources);

/* Output cJSON to stdout (handles memory cleanup) */
void json_print_and_free(cJSON *json, int formatted);

#endif /* JSON_UTILS_H */
```

```c
// src/json_utils.c
#include "json_utils.h"
#include <stdio.h>

void reading_add_to_json(cJSON *obj, const ChannelReading *reading) {
    if (reading->has_temp) {
        cJSON_AddNumberToObject(obj, "TEMPERATURE", reading->temperature);
    }
    if (reading->has_adc) {
        cJSON_AddNumberToObject(obj, "ADC", reading->adc_voltage);
    }
    if (reading->has_cjc) {
        cJSON_AddNumberToObject(obj, "CJC", reading->cjc_temp);
    }
}

cJSON* reading_to_json(const ChannelReading *reading) {
    cJSON *obj = cJSON_CreateObject();
    cJSON_AddNumberToObject(obj, "ADDRESS", reading->address);
    cJSON_AddNumberToObject(obj, "CHANNEL", reading->channel);
    reading_add_to_json(obj, reading);
    return obj;
}

void json_print_and_free(cJSON *json, int formatted) {
    char *str = formatted ? cJSON_Print(json) : cJSON_PrintUnformatted(json);
    printf("%s\n", str);
    fflush(stdout);
    free(str);
    cJSON_Delete(json);
}
```

---

### 5.2 Consolidate all JSON output functions

Replace these functions with calls to the new helpers:
- `thermo_data_output_json()` in `src/commands/get.c`
- `output_single_json_with_key()` in `src/commands/get.c`
- `output_channels_json()` in `src/commands/get.c`
- `get_thermal_data()` in `src/bridge.c`

---

## Phase 6: Build System Improvements

### 6.1 Add dependency tracking

**File:** `Makefile`

```makefile
# Add after CFLAGS definition
DEPFLAGS = -MMD -MP
CFLAGS += $(DEPFLAGS)

# Add before .PHONY
-include $(OBJECTS:.o=.d)

# Update clean target
clean:
	@echo "Cleaning build artifacts..."
	rm -f $(OBJECTS) $(OBJECTS:.o=.d) $(TARGET)
	@echo "Clean complete"
```

---

### 6.2 Add sanitizers for debug builds (optional)

```makefile
ifeq ($(DEBUG),1)
    CFLAGS += -g -DDEBUG -O0
    # Uncomment for memory debugging (requires libasan)
    # CFLAGS += -fsanitize=address -fsanitize=undefined
    # LDFLAGS += -fsanitize=address -fsanitize=undefined
    $(info Building in DEBUG mode)
else
    CFLAGS += -O2
endif
```

---

### 6.3 Add new source files

Update SOURCES as new files are added:

```makefile
SOURCES = src/main.c \
          src/commands/list.c \
          src/commands/get.c \
          src/commands/set.c \
          src/commands/init_config.c \
          src/hardware.c \
          src/common.c \
          src/bridge.c \
          src/utils.c \
          src/signals.c \
          src/board_manager.c \
          src/json_utils.c \
          vendor/cJSON.c
```

---

## Phase 7: Testing & Documentation

### 7.1 Create mock hardware layer for testing

**New files:** `test/mock_hardware.c`, `test/mock_hardware.h`

```c
// test/mock_hardware.h
#ifndef MOCK_HARDWARE_H
#define MOCK_HARDWARE_H

/* Mock implementations for testing without hardware */
/* Compile with -DMOCK_HARDWARE to use */

#endif /* MOCK_HARDWARE_H */
```

```c
// test/mock_hardware.c
#ifdef MOCK_HARDWARE

#include "hardware.h"
#include <string.h>

static uint8_t mock_boards_open[8] = {0};

int thermo_open(uint8_t address) {
    if (address > 7) return THERMO_INVALID_PARAM;
    mock_boards_open[address] = 1;
    return THERMO_SUCCESS;
}

int thermo_close(uint8_t address) {
    if (address > 7) return THERMO_INVALID_PARAM;
    mock_boards_open[address] = 0;
    return THERMO_SUCCESS;
}

int thermo_is_open(uint8_t address) {
    if (address > 7) return 0;
    return mock_boards_open[address];
}

int thermo_list_boards(struct HatInfo **boards, int *count) {
    /* Return 2 mock boards */
    *count = 2;
    *boards = malloc(2 * sizeof(struct HatInfo));
    (*boards)[0].address = 0;
    strcpy((*boards)[0].product_name, "MCC 134 (Mock)");
    (*boards)[1].address = 1;
    strcpy((*boards)[1].product_name, "MCC 134 (Mock)");
    return THERMO_SUCCESS;
}

int thermo_read_temp(uint8_t address, uint8_t channel, double *value) {
    /* Return deterministic test values */
    *value = 25.0 + (address * 10.0) + (channel * 2.5);
    return THERMO_SUCCESS;
}

int thermo_read_adc(uint8_t address, uint8_t channel, double *value) {
    *value = 0.001 * (address + 1) * (channel + 1);
    return THERMO_SUCCESS;
}

int thermo_read_cjc(uint8_t address, uint8_t channel, double *value) {
    *value = 22.0 + channel * 0.5;
    return THERMO_SUCCESS;
}

int thermo_get_serial(uint8_t address, char *buffer, size_t len) {
    snprintf(buffer, len, "MOCK%04d", address);
    return THERMO_SUCCESS;
}

int thermo_get_calibration_date(uint8_t address, char *buffer, size_t len) {
    snprintf(buffer, len, "2025-01-01");
    return THERMO_SUCCESS;
}

int thermo_get_calibration_coeffs(uint8_t address, uint8_t channel, CalibrationInfo *cal) {
    cal->slope = 1.0;
    cal->offset = 0.0;
    return THERMO_SUCCESS;
}

int thermo_set_calibration_coeffs(uint8_t address, uint8_t channel, double slope, double offset) {
    (void)address; (void)channel; (void)slope; (void)offset;
    return THERMO_SUCCESS;
}

int thermo_get_update_interval(uint8_t address, uint8_t *interval) {
    *interval = 1;
    return THERMO_SUCCESS;
}

int thermo_set_update_interval(uint8_t address, uint8_t interval) {
    (void)address; (void)interval;
    return THERMO_SUCCESS;
}

int thermo_set_tc_type(uint8_t address, uint8_t channel, const char *tc_type_str) {
    (void)address; (void)channel; (void)tc_type_str;
    return THERMO_SUCCESS;
}

uint8_t thermo_tc_type_from_string(const char *tc_type_str) {
    if (strcmp(tc_type_str, "K") == 0) return 1;
    if (strcmp(tc_type_str, "J") == 0) return 0;
    if (strcmp(tc_type_str, "T") == 0) return 2;
    return 8; /* TC_DISABLED */
}

void thermo_wait_for_readings(void) {
    /* No-op for mock */
}

#endif /* MOCK_HARDWARE */
```

---

### 7.2 Add test targets to Makefile

```makefile
# Test targets
.PHONY: test test-mock

test: $(TARGET)
	@echo "Running basic tests..."
	./$(TARGET) --version
	./$(TARGET) --help
	./$(TARGET) list --help
	./$(TARGET) get --help
	./$(TARGET) set --help
	./$(TARGET) fuse --help 2>/dev/null || true
	./$(TARGET) init-config --help
	@echo "Basic tests passed!"

# Build with mock hardware for testing without actual boards
MOCK_SOURCES = $(filter-out src/hardware.c,$(SOURCES)) test/mock_hardware.c
MOCK_OBJECTS = $(MOCK_SOURCES:.c=.o)
MOCK_TARGET = thermo-cli-mock

$(MOCK_TARGET): CFLAGS += -DMOCK_HARDWARE
$(MOCK_TARGET): $(MOCK_OBJECTS)
	$(CC) -o $@ $^ $(LDFLAGS)

test-mock: $(MOCK_TARGET)
	@echo "Running mock hardware tests..."
	./$(MOCK_TARGET) list
	./$(MOCK_TARGET) list --json
	./$(MOCK_TARGET) get --temp
	./$(MOCK_TARGET) get --temp --adc --cjc --json
	./$(MOCK_TARGET) get -a 1 -c 2 --temp
	@echo "Mock tests passed!"

clean-mock:
	rm -f $(MOCK_OBJECTS) $(MOCK_TARGET)
```

---

### 7.3 Add CI configuration (optional)

**.github/workflows/build.yml:**

```yaml
name: Build and Test

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y libyaml-dev
          
      - name: Build
        run: make
        
      - name: Build mock
        run: make $(MOCK_TARGET)
        
      - name: Test
        run: make test-mock
```

---

## Checklist

### Phase 1: Quick Fixes
- [ ] 1.1 Fix `DAFAULT_*` → `DEFAULT_*` typos
- [ ] 1.2 Fix memory leaks in `output_channels_table()`
- [ ] 1.3 Fix `set` command opening board twice
- [ ] 1.4 Add input validation helpers
- [ ] 1.5 Check `fread()` return value

### Phase 2: Signal Handling
- [ ] 2.1 Create `signals.h` and `signals.c`
- [ ] 2.2 Update `stream_channels()` to use signal handling
- [ ] 2.3 Update bridge streaming
- [ ] 2.4 Update Makefile

### Phase 3: Data Structure Refactoring
- [ ] 3.1 Define new structures (`ChannelConfig`, `BoardInfo`, `ChannelReading`)
- [ ] 3.2 Create adapter functions
- [ ] 3.3 Migrate functions incrementally

### Phase 4: Board Manager Module
- [ ] 4.1 Create `board_manager.h` and `board_manager.c`
- [ ] 4.2 Refactor `get.c` to use BoardManager
- [ ] 4.3 Refactor `bridge.c` to use BoardManager

### Phase 5: JSON Output Consolidation
- [ ] 5.1 Create `json_utils.h` and `json_utils.c`
- [ ] 5.2 Consolidate JSON output functions

### Phase 6: Build System
- [ ] 6.1 Add dependency tracking (`-MMD -MP`)
- [ ] 6.2 Add sanitizer options (optional)
- [ ] 6.3 Add new source files to Makefile

### Phase 7: Testing
- [ ] 7.1 Create mock hardware layer
- [ ] 7.2 Add test targets to Makefile
- [ ] 7.3 Add CI configuration (optional)

---

## Notes

- Each phase should be completed and tested before moving to the next
- Commit after each sub-task for easy rollback
- Run `make clean && make` after each phase to verify no regressions
- Consider creating a branch for larger refactoring phases (3, 4)
