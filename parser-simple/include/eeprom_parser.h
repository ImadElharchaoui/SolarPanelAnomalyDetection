#pragma once

#include "types.h"
#include <string_view>
#include <vector>

// Global buffers to hold parsed EEPROM data
extern DailyLogBuffer g_daily_logs;
extern MonthlyLogBuffer g_monthly_logs;
extern EepromSettings g_eeprom_settings;

auto parse_eeprom_dump(std::string_view line) -> bool;
