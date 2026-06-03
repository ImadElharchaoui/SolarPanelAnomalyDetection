#include "eeprom_parser.h"

#include <sstream>
#include <iomanip>
#include <cstring>
#include <algorithm>

#include "constants.h"
#include "utils.h"

// Global buffers to hold parsed EEPROM data
DailyLogBuffer g_daily_logs;
MonthlyLogBuffer g_monthly_logs;
EepromSettings g_eeprom_settings;

// Generic parser for a single 16-byte log block (Daily or Monthly)
static auto parse_log_block(const std::vector<uint8_t> &data, int offset, uint16_t index, LogEntry &entry) -> bool {
    if ((static_cast<size_t>(offset) + EEPROM_DAILY_BLOCK_SIZE) > data.size()) {
        return false;
    }

    // Skip blocks with no meaningful data
    bool blank = (byte_at(data, offset) == 0 && byte_at(data, offset + 1) == 0 &&
                  get_u16(data, offset + 2) == 0 && get_u16(data, offset + 4) == 0);
    if (blank) {
        return false;
    }

    entry.index           = index;
    entry.vbat_max_mv     = byte_at(data, offset);
    entry.vbat_min_mv     = byte_at(data, offset + 1);
    entry.ah_charge_mah   = get_u16(data, offset + 2);
    entry.ah_load_mah     = get_u16(data, offset + 4);
    entry.vpv_max_mv      = byte_at(data, offset + 6);
    entry.vpv_min_mv      = byte_at(data, offset + 7);
    entry.il_max_ma       = byte_at(data, offset + 8);
    entry.ipv_max_ma      = byte_at(data, offset + 9);
    entry.soc_pct         = byte_at(data, offset + 10);
    entry.ext_temp_max_c  = static_cast<int8_t>(byte_at(data, offset + 11));
    entry.ext_temp_min_c  = static_cast<int8_t>(byte_at(data, offset + 12));
    entry.nightlength_min = byte_at(data, offset + 13);
    entry.state           = StateFlags::parse(get_u16(data, offset + 14));

    return true;
}

// Reads the daily circular buffer into daily_logs
static void parse_daily_logs(const std::vector<uint8_t> &data, uint16_t num_days, DailyLogBuffer &daily_logs) {
    const int NUM_ENTRIES = std::min(static_cast<int>(num_days), EEPROM_DAILY_MAX_BLOCKS);
    if (NUM_ENTRIES <= 0) {
        return;
    }

    // The write pointer wraps at EEPROM_DAILY_MAX_BLOCKS; the oldest populated
    // slot is at (num_days % MAX) when the ring is full.
    const int START_BUF = (num_days - NUM_ENTRIES) % EEPROM_DAILY_MAX_BLOCKS;

    for (int i = 0; i < NUM_ENTRIES; ++i) {
        const int BUF_IDX = (START_BUF + i) % EEPROM_DAILY_MAX_BLOCKS;
        const int OFFSET  = EEPROM_DAILY_START_OFFSET + (BUF_IDX * EEPROM_DAILY_BLOCK_SIZE);

        LogEntry day;
        if (parse_log_block(data, OFFSET, static_cast<uint16_t>(i + 1), day)) {
            daily_logs.entries[daily_logs.count++] = day;
        }
    }
}

// Reads the monthly circular buffer into monthly_logs
static void parse_monthly_logs(const std::vector<uint8_t> &data, uint16_t num_days, MonthlyLogBuffer &monthly_logs) {
    const int TOTAL_MONTHS = num_days / 31;
    const int NUM_MONTHLY  = std::min(TOTAL_MONTHS, EEPROM_MONTHLY_MAX_BLOCKS);

    if (NUM_MONTHLY <= 0) {
        return;
    }

    const int START_MBUF = (TOTAL_MONTHS - NUM_MONTHLY) % EEPROM_MONTHLY_MAX_BLOCKS;

    for (int i = 0; i < NUM_MONTHLY; ++i) {
        const int BUF_IDX = (START_MBUF + i) % EEPROM_MONTHLY_MAX_BLOCKS;
        const int OFFSET  = EEPROM_MONTHLY_START_OFFSET + (BUF_IDX * EEPROM_MONTHLY_BLOCK_SIZE);

        LogEntry mo;
        if (parse_log_block(data, OFFSET, static_cast<uint16_t>(i + 1), mo)) {
            monthly_logs.entries[monthly_logs.count++] = mo;
        }
    }
}

auto parse_eeprom_dump(std::string_view line) -> bool {
    // Skip the leading '!' character if present
    if (!line.empty() && line[0] == '!') {
        line = line.substr(1);
    }
    
    auto data = parse_hex_dump(line);
    if (data.size() < 144) {
        return false;
    }
    
    // Parse datalogger summary (contains num_days)
    const int S = EEPROM_DATALOG_SUMMARY_OFFSET;
    if (S + 16 > static_cast<int>(data.size())) {
        return false;
    }

    uint16_t num_days = get_u16(data, S + 14);
    
    if (num_days == 0) {
        return false;
    }

    // Parse daily and monthly logs
    parse_daily_logs(data, num_days, g_daily_logs);
    parse_monthly_logs(data, num_days, g_monthly_logs);

    return (g_daily_logs.count > 0);
}
