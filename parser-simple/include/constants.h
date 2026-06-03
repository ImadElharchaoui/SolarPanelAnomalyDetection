#pragma once

#include <cstddef>

// Protocol field counts
constexpr int EXPECTED_FIELDS_V2 = 27;
constexpr int EXPECTED_FIELDS_V3 = 42;

// Space Command field indices
constexpr int FIELD_CHARGE_CURRENT_MA  = 1;
constexpr int FIELD_LOAD_CURRENT_MA    = 2;
constexpr int FIELD_PV_VOLTAGE_MV      = 6;
constexpr int FIELD_PV_TARGET_MV       = 7;
constexpr int FIELD_PWM_COUNTS         = 8;
constexpr int FIELD_FIRMWARE_VERSION   = 12;
constexpr int FIELD_LOAD_STATE_RAW     = 13;
constexpr int FIELD_CHARGE_STATE_RAW   = 14;
constexpr int FIELD_BATTERY_VOLTAGE_MV = 15;
constexpr int FIELD_BAT_THRESHOLD_MV   = 16;
constexpr int FIELD_BATTERY_SOC_PCT    = 17;
constexpr int FIELD_INTERNAL_TEMP_C    = 18;
constexpr int FIELD_EXTERNAL_TEMP_C    = 19;
constexpr int FIELD_MPP_STATE          = 21;
constexpr int FIELD_HVD_STATE          = 22;
constexpr int FIELD_LOAD_STATE2_RAW    = 24;
constexpr int FIELD_NIGHTLENGTH_MIN    = 25;
constexpr int FIELD_AVG_NIGHTLENGTH    = 26;
constexpr int FIELD_LED_VOLTAGE_MV     = 28;
constexpr int FIELD_LED_CURRENT_MA     = 29;
constexpr int FIELD_LED_STATUS         = 30;
constexpr int FIELD_DALI_ACTIVE        = 31;
constexpr int FIELD_OP_DAYS            = 32;
constexpr int FIELD_BAT_OP_DAYS        = 33;
constexpr int FIELD_ENERGY_IN_WH       = 34;
constexpr int FIELD_ENERGY_OUT_WH      = 35;
constexpr int FIELD_ENERGY_RETAINED_WH = 36;
constexpr int FIELD_CHARGE_POWER_W     = 37;
constexpr int FIELD_LOAD_POWER_W       = 38;
constexpr int FIELD_LED_POWER_W        = 39;
constexpr int FIELD_FAULT_STATUS       = 40;
constexpr int FIELD_PV_DETECTED        = 41;
constexpr int FIELD_BATTERY_DETECTED   = 42;

constexpr size_t FIELD_BUF_SIZE   = 24;
constexpr size_t MIN_RESPONSE_LEN = 80;

// EEPROM byte offsets and sizes
constexpr size_t EEPROM_HOURLY_RESERVE     = 2;
constexpr int EEPROM_DATALOG_SUMMARY_OFFSET = 128;
constexpr int EEPROM_DAILY_START_OFFSET     = 144;
constexpr int EEPROM_DAILY_BLOCK_SIZE       = 16;
constexpr int EEPROM_DAILY_MAX_BLOCKS       = 30;
constexpr int EEPROM_MONTHLY_START_OFFSET   = 624;
constexpr int EEPROM_MONTHLY_BLOCK_SIZE     = 16;
constexpr int EEPROM_MONTHLY_MAX_BLOCKS     = 24;
