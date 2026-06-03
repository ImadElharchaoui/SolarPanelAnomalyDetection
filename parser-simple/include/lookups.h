#pragma once

#include <cstdint>
#include "types.h"

inline auto charge_mode_from_state(int charge_state) -> ChargeMode {
    if ((charge_state & 0x20) == 0x20) {
        return ChargeMode::CHARGE_MODE_DISABLED;
    }
    if ((charge_state & 0x01) == 0x01) {
        return ChargeMode::CHARGE_MODE_BOOST;
    }
    if ((charge_state & 0x02) == 0x02) {
        return ChargeMode::CHARGE_MODE_EQUALIZATION;
    }
    return ChargeMode::CHARGE_MODE_FLOAT;
}

inline auto charge_mode_to_string(ChargeMode mode) -> const char * {
    switch (mode) {
        case ChargeMode::CHARGE_MODE_FLOAT:
            return "Float";
        case ChargeMode::CHARGE_MODE_BOOST:
            return "Boost";
        case ChargeMode::CHARGE_MODE_EQUALIZATION:
            return "Equalization";
        case ChargeMode::CHARGE_MODE_DISABLED:
            return "Disabled";
        default:
            return "Unknown";
    }
}

inline auto lvd_mode_to_string(LvdMode mode) -> const char * {
    switch (mode) {
        case LvdMode::LVD_MODE_SOC:
            return "SOC";
        case LvdMode::LVD_MODE_VOLTAGE:
            return "Voltage";
        default:
            return "Unknown";
    }
}

inline auto led_status_name(uint8_t s) -> const char * {
    switch (s) {
        case 0:
            return "Normal";
        case 1:
            return "Short";
        case 2:
            return "Open";
        default:
            return "Unknown";
    }
}

inline auto battery_type_to_string(BatteryType type) -> const char * {
    switch (type) {
        case BatteryType::BATTERY_AGM:
            return "AGM/Gel";
        case BatteryType::BATTERY_LIQUID:
            return "Liquid";
        case BatteryType::BATTERY_LFP:
            return "LiFePO4";
        case BatteryType::BATTERY_LFP_HIGH_TEMP:
            return "LiFePO4 - High Temp";
        case BatteryType::BATTERY_LFP_MEDIUM_TEMP:
            return "LiFePO4 - Medium Temp";
        case BatteryType::BATTERY_LFP_LOW_TEMP:
            return "LiFePO4 - Low Temp";
        default:
            return "Unknown";
    }
}

inline auto battery_type_name(int idx, int hw_version) -> BatteryType {
    if (hw_version == 2) {
        switch (idx) {
            case 0:
                return BatteryType::BATTERY_AGM;
            case 1:
                return BatteryType::BATTERY_LIQUID;
            case 2:
                return BatteryType::BATTERY_LFP;
            default:
                return BatteryType::BATTERY_AGM;
        }
    } else {
        switch (idx) {
            case 0:
                return BatteryType::BATTERY_LFP_HIGH_TEMP;
            case 1:
                return BatteryType::BATTERY_LFP_MEDIUM_TEMP;
            case 2:
                return BatteryType::BATTERY_LFP_LOW_TEMP;
            default:
                return BatteryType::BATTERY_LFP_HIGH_TEMP;
        }
    }
}

inline auto resolve_hw_version(bool have_eeprom, uint8_t eeprom_hwver, bool have_tele, uint8_t tele_hwver) -> uint8_t {
    if (have_eeprom) {
        return eeprom_hwver;
    }
    if (have_tele) {
        return tele_hwver;
    }
    return 3;
}

inline auto night_mode_to_string(NightMode mode) -> const char * {
    switch (mode) {
        case NightMode::NIGHT_MODE_OFF:
            return "Off";
        case NightMode::NIGHT_MODE_D2D:
            return "D2D";
        case NightMode::NIGHT_MODE_DD:
            return "DD";
        case NightMode::NIGHT_MODE_MN:
            return "MN";
        default:
            return "Unknown";
    }
}
