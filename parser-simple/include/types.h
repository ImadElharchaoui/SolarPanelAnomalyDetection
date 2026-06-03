#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include "constants.h"

// Simple enums to replace protobuf (no protobuf dependency!)
enum BatteryType : uint8_t {
    BATTERY_AGM = 0,
    BATTERY_LIQUID = 1,
    BATTERY_LFP = 2,
    BATTERY_LFP_HIGH_TEMP = 3,
    BATTERY_LFP_MEDIUM_TEMP = 4,
    BATTERY_LFP_LOW_TEMP = 5,
};

enum NightMode : uint8_t {
    NIGHT_MODE_OFF = 0,
    NIGHT_MODE_D2D = 1,
    NIGHT_MODE_DD = 2,
    NIGHT_MODE_MN = 3,
};

enum ChargeMode : uint8_t {
    CHARGE_MODE_FLOAT = 0,
    CHARGE_MODE_BOOST = 1,
    CHARGE_MODE_EQUALIZATION = 2,
    CHARGE_MODE_DISABLED = 3,
};

enum LvdMode : uint8_t {
    LVD_MODE_SOC = 0,
    LVD_MODE_VOLTAGE = 1,
};


// Parsed from Space line field 13 (loadState bitmask)
struct LoadStatusFlags {
    bool load_disconnected = false;
    bool night_mode_active = false;
    bool lvd_active = false;
    bool user_disconnect = false;
    bool low_temp = false;
    bool high_temp = false;
    bool over_current = false;

    static auto parse(uint16_t v) -> LoadStatusFlags {
        LoadStatusFlags f;
        f.load_disconnected = (v & 0x001) != 0;
        f.night_mode_active = (v & 0x002) != 0;
        f.lvd_active = (v & 0x004) != 0;
        f.user_disconnect = (v & 0x008) != 0;
        f.low_temp = (v & 0x010) != 0;
        f.high_temp = (v & 0x020) != 0;
        f.over_current = (v & 0x100) != 0;
        return f;
    }

    [[nodiscard]] auto load_on() const -> bool {
        return !load_disconnected;
    }
};

struct ChargeStatusFlags {
    bool boost_charge = false;
    bool equalization_charge = false;
    bool is_night = false;
    bool dimming_override = false;
    bool ssr_output = false;

    static auto parse(uint16_t v) -> ChargeStatusFlags {
        ChargeStatusFlags f;
        f.boost_charge = (v & 0x01) != 0;
        f.equalization_charge = (v & 0x02) != 0;
        f.is_night = (v & 0x08) != 0;
        f.dimming_override = (v & 0x40) != 0;
        f.ssr_output = (v & 0x80) != 0;
        return f;
    }
};

struct FaultStatusFlags {
    bool battery_over_voltage = false;
    bool pv_over_voltage = false;
    bool controller_over_temp = false;
    bool charge_over_current = false;
    bool lvd_active = false;
    bool over_discharge_current = false;
    bool battery_over_temp = false;
    bool battery_under_temp = false;

    static auto parse(uint16_t v) -> FaultStatusFlags {
        FaultStatusFlags f;
        f.battery_over_voltage = (v & 0x01) != 0;
        f.pv_over_voltage = (v & 0x02) != 0;
        f.controller_over_temp = (v & 0x04) != 0;
        f.charge_over_current = (v & 0x08) != 0;
        f.lvd_active = (v & 0x10) != 0;
        f.over_discharge_current = (v & 0x20) != 0;
        f.battery_over_temp = (v & 0x40) != 0;
        f.battery_under_temp = (v & 0x80) != 0;
        return f;
    }

    [[nodiscard]] auto to_bitmask() const -> uint32_t {
        uint32_t v = 0;
        if (battery_over_voltage) v |= (1U << 0);
        if (pv_over_voltage) v |= (1U << 1);
        if (controller_over_temp) v |= (1U << 2);
        if (charge_over_current) v |= (1U << 3);
        if (lvd_active) v |= (1U << 4);
        if (over_discharge_current) v |= (1U << 5);
        if (battery_over_temp) v |= (1U << 6);
        if (battery_under_temp) v |= (1U << 7);
        return v;
    }

    [[nodiscard]] auto any() const -> bool {
        return to_bitmask() != 0;
    }
};

struct DeviceSettings {
    std::optional<BatteryType> battery_type;
    uint16_t capacity_ah = 0;
    uint16_t lvd_voltage_mv = 0;
    uint16_t lvd_level_current_mv = 0;
    uint16_t lvd_level_voltage_mv = 0;
    bool lvd_mode_voltage = false;

    std::optional<NightMode> night_mode_index;
    uint16_t evening_minutes = 0;
    uint16_t morning_minutes = 0;
    uint16_t night_threshold_mv = 0;

    std::optional<NightMode> night_mode_dimming_index;
    uint16_t evening_minutes_dimming = 0;
    uint16_t morning_minutes_dimming = 0;
    uint8_t dimming_pct = 0;
    uint8_t base_dimming_pct = 0;

    bool dali_power_enable = false;
    bool alc_dimming_enable = false;
    bool reset_battery_opt = false;

    uint8_t hw_version = 3;
    bool load_disconnect_mode = false;
};

struct PhocosTelemetry {
    uint32_t firmware_version = 0;
    int16_t internal_temp_c = 0;
    int16_t external_temp_c = 0;
    uint16_t op_days = 0;

    uint32_t battery_voltage_mv = 0;
    uint8_t battery_soc_pct = 0;
    uint32_t charge_current_ma10 = 0;
    uint32_t battery_threshold_mv = 0;
    uint16_t bat_op_days = 0;
    uint16_t energy_in_daily_wh = 0;
    uint16_t energy_out_daily_wh = 0;
    uint16_t energy_retained_wh = 0;
    uint16_t charge_power_w = 0;
    uint8_t battery_detected = 0;

    uint32_t load_current_ma10 = 0;
    uint16_t load_power_w = 0;

    uint32_t pv_voltage_mv = 0;
    uint32_t pv_target_mv = 0;
    uint8_t pv_detected = 0;
    uint16_t pwm_counts = 0;

    uint16_t nightlength_min = 0;
    uint16_t avg_nightlength_min = 0;

    uint32_t led_voltage_mv = 0;
    uint32_t led_current_ma10 = 0;
    uint16_t led_power_w = 0;
    uint8_t led_status = 0;
    uint8_t dali_active = 0;

    uint16_t charge_state_raw = 0;
    uint16_t load_state_raw = 0;
    uint16_t load_state2_raw = 0;
    uint8_t mpp_state = 0;
    uint8_t hvd_state = 0;

    LoadStatusFlags load_flags = {};
    ChargeStatusFlags charge_flags = {};
    FaultStatusFlags fault_flags = {};
    uint16_t fault_status = 0;

    uint8_t hw_version = 3;

    [[nodiscard]] auto to_bitmask() const -> uint32_t {
        uint32_t f = 0;
        if (battery_detected != 0U) f |= (1U << 0);
        if (charge_flags.is_night) f |= (1U << 1);
        if (load_flags.load_on()) f |= (1U << 2);
        if (load_flags.night_mode_active) f |= (1U << 3);
        if (load_flags.lvd_active) f |= (1U << 4);
        if (load_flags.user_disconnect) f |= (1U << 5);
        if (load_flags.over_current) f |= (1U << 6);
        if (pv_detected != 0U) f |= (1U << 7);
        if (dali_active != 0U) f |= (1U << 8);
        return f;
    }
};

struct StateFlags {
    bool load_disconnect = false;
    bool full_charge = false;
    bool pv_over_current = false;
    bool load_over_current = false;
    bool battery_over_voltage = false;
    bool low_soc = false;
    bool temp_over_pv_over = false;
    bool temp_over_pv_low = false;
    bool temp_over_load_over = false;

    static auto parse(uint16_t v) -> StateFlags {
        StateFlags f;
        f.load_disconnect = (v & 0x0001) != 0;
        f.full_charge = (v & 0x0002) != 0;
        f.pv_over_current = (v & 0x0004) != 0;
        f.load_over_current = (v & 0x0008) != 0;
        f.battery_over_voltage = (v & 0x0010) != 0;
        f.low_soc = (v & 0x0020) != 0;
        f.temp_over_pv_over = (v & 0x0040) != 0;
        f.temp_over_pv_low = (v & 0x0080) != 0;
        f.temp_over_load_over = (v & 0x0100) != 0;
        return f;
    }

    [[nodiscard]] auto to_bitmask() const -> uint32_t {
        uint32_t v = 0;
        if (load_disconnect) v |= (1U << 0);
        if (full_charge) v |= (1U << 1);
        if (pv_over_current) v |= (1U << 2);
        if (load_over_current) v |= (1U << 3);
        if (battery_over_voltage) v |= (1U << 4);
        if (low_soc) v |= (1U << 5);
        if (temp_over_pv_over) v |= (1U << 6);
        if (temp_over_pv_low) v |= (1U << 7);
        if (temp_over_load_over) v |= (1U << 8);
        return v;
    }
};

struct LogEntry {
    uint16_t index = 0;
    uint8_t vbat_max_mv = 0;
    uint8_t vbat_min_mv = 0;
    uint16_t ah_charge_mah = 0;
    uint16_t ah_load_mah = 0;
    uint8_t vpv_max_mv = 0;
    uint8_t vpv_min_mv = 0;
    uint8_t il_max_ma = 0;
    uint8_t ipv_max_ma = 0;
    uint8_t soc_pct = 0;
    int8_t ext_temp_max_c = 0;
    int8_t ext_temp_min_c = 0;
    uint16_t total_ah_charge = 0;
    uint16_t total_ah_load = 0;
    uint32_t nightlength_min = 0;

    StateFlags state;
};

struct HumanLogEntry {
    float vbat_max_v;
    float vbat_min_v;
    float ah_charge_mah;
    float ah_load_mah;
    float vpv_max_v;
    float vpv_min_v;
    float il_max_ma;
    float ipv_max_ma;
    float soc_pct;
    int8_t ext_temp_max_c;
    int8_t ext_temp_min_c;
    uint32_t nightlength_min;
};

inline auto to_human_log(const LogEntry &e) -> HumanLogEntry {
    return {
        static_cast<float>(e.vbat_max_mv) / 100.0f,
        static_cast<float>(e.vbat_min_mv) / 100.0f,
        static_cast<float>(e.ah_charge_mah),
        static_cast<float>(e.ah_load_mah),
        static_cast<float>(e.vpv_max_mv) / 100.0f,
        static_cast<float>(e.vpv_min_mv) / 100.0f,
        static_cast<float>(e.il_max_ma),
        static_cast<float>(e.ipv_max_ma),
        static_cast<float>(e.soc_pct),
        e.ext_temp_max_c,
        e.ext_temp_min_c,
        e.nightlength_min,
    };
}

struct DailyLogBuffer {
    std::array<LogEntry, EEPROM_DAILY_MAX_BLOCKS> entries{};
    std::size_t count = 0;
};

struct MonthlyLogBuffer {
    std::array<LogEntry, EEPROM_MONTHLY_MAX_BLOCKS> entries{};
    std::size_t count = 0;
};

struct EepromSettings {
    std::string device_id;
    std::string serial_number;
    std::string production_date;
    uint8_t hw_version = 3;

    DeviceSettings settings;

    std::string battery_type;
    std::string night_mode;
    std::string night_mode_dimming;

    uint16_t battery_op_days = 0;
    uint16_t operation_days = 0;

    uint16_t equalization_mv = 0;
    uint16_t boost_mv = 0;
    uint16_t float_mv = 0;
    int16_t temp_comp_mv_per_c = 0;
};

struct DataloggerSummary {
    uint16_t days_with_lvd = 0;
    uint8_t months_without_full_charge = 0;
    uint16_t avg_morning_soc_pct = 0;
    uint32_t total_ah_charge = 0;
    uint32_t total_ah_load = 0;
    uint16_t num_days = 0;
};
