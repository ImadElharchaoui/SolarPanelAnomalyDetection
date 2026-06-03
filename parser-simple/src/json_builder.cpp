#include "json_builder.h"

#include "lookups.h"
#include "utils.h"

using json = nlohmann::json;

static inline auto v16(uint16_t mv) -> double {
    return mv_to_v(static_cast<uint32_t>(mv));
}

auto build_telemetry_json(const PhocosTelemetry &t,
                          const EepromSettings  &settings,
                          std::time_t            ts,
                          JsonScalingFormat      scaling_format) -> nlohmann::json {
    nlohmann::json j;

    double v_div = (scaling_format == JsonScalingFormat::SCALED) ? 1000.0 : 1.0;
    double a_div = (scaling_format == JsonScalingFormat::SCALED) ? 1000.0 : 1.0;

    j["general"] = {
        {"timestamp", static_cast<long long>(ts)},
        {"serial_number", settings.serial_number},
        {"firmware_version", t.firmware_version},
        {"internal_temp_c", t.internal_temp_c},
        {"external_temp_c", t.external_temp_c},
        {"controller_op_days", t.op_days},
        {"hw_version", t.hw_version},
    };

    j["battery"] = {
        {"voltage_v", static_cast<double>(t.battery_voltage_mv) / v_div},
        {"soc_pct", t.battery_soc_pct},
        {"charge_current_a", static_cast<double>(t.charge_current_ma10 * 10) / a_div},
        {"charge_power_w", t.charge_power_w},
        {"end_of_charge_voltage_v", static_cast<double>(t.battery_threshold_mv) / v_div},
        {"charge_mode", charge_mode_to_string(charge_mode_from_state(t.charge_state_raw))},
        {"is_night", t.charge_flags.is_night},
        {"operation_days", t.bat_op_days},
        {"energy_in_daily_wh", t.energy_in_daily_wh},
        {"energy_out_daily_wh", t.energy_out_daily_wh},
        {"energy_retained_wh", t.energy_retained_wh},
        {"detected", static_cast<bool>(t.battery_detected)},
    };

    j["load"] = {
        {"load_on", t.load_flags.load_on()},
        {"night_mode", t.load_flags.night_mode_active},
        {"lvd_active", t.load_flags.lvd_active},
        {"user_disconnect", t.load_flags.user_disconnect},
        {"over_current", t.load_flags.over_current},
        {"current_a", static_cast<double>(t.load_current_ma10 * 10) / a_div},
        {"power_w", t.load_power_w},
    };

    j["pv"] = {
        {"voltage_v", static_cast<double>(t.pv_voltage_mv) / v_div},
        {"target_voltage_v", static_cast<double>(t.pv_target_mv) / v_div},
        {"detected", static_cast<bool>(t.pv_detected)},
    };

    j["night"] = {
        {"time_since_dusk_min", t.nightlength_min},
        {"average_length_min", t.avg_nightlength_min},
    };

    j["led"] = {
        {"voltage_v", static_cast<double>(t.led_voltage_mv) / v_div},
        {"current_a", static_cast<double>(t.led_current_ma10 * 10) / a_div},
        {"power_w", t.led_power_w},
        {"status", led_status_name(t.led_status)},
        {"dali_active", static_cast<bool>(t.dali_active)},
    };

    j["faults"] = {
        {"battery_over_voltage", t.fault_flags.battery_over_voltage},
        {"pv_over_voltage", t.fault_flags.pv_over_voltage},
        {"controller_over_temp", t.fault_flags.controller_over_temp},
        {"charge_over_current", t.fault_flags.charge_over_current},
        {"lvd_active", t.load_flags.lvd_active || t.fault_flags.lvd_active},
        {"over_discharge_current", t.fault_flags.over_discharge_current},
        {"load_over_current", t.load_flags.over_current},
        {"battery_over_temp", t.fault_flags.battery_over_temp || t.load_flags.high_temp},
        {"battery_under_temp", t.fault_flags.battery_under_temp || t.load_flags.low_temp},
    };

    return j;
}

auto build_daily_logs_json(const DailyLogBuffer &logs) -> nlohmann::json {
    nlohmann::json j = nlohmann::json::array();
    
    for (size_t i = 0; i < logs.count; ++i) {
        const auto &entry = logs.entries[i];
        
        nlohmann::json log_entry = {
            {"day", entry.index},
            {"vbat_min_v", static_cast<float>(entry.vbat_min_mv) / 10.0f},
            {"vbat_max_v", static_cast<float>(entry.vbat_max_mv) / 10.0f},
            {"ah_charge_ah", static_cast<float>(entry.ah_charge_mah) / 10.0f},
            {"ah_load_ah", static_cast<float>(entry.ah_load_mah) / 10.0f},
            {"vpv_min_v", static_cast<float>(entry.vpv_min_mv) * 0.5f},
            {"vpv_max_v", static_cast<float>(entry.vpv_max_mv) * 0.5f},
            {"il_max_a", static_cast<float>(entry.il_max_ma) * 0.5f},
            {"ipv_max_a", static_cast<float>(entry.ipv_max_ma) * 0.5f},
            {"soc_pct", static_cast<float>(entry.soc_pct) * 6.6f},
            {"text_min_c", entry.ext_temp_min_c},
            {"text_max_c", entry.ext_temp_max_c},
            {"night_h", static_cast<float>(entry.nightlength_min) / 6.0f},
        };
        j.push_back(log_entry);
    }
    
    return j;
}
