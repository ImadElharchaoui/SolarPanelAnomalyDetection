#pragma once

#include "json.hpp"
#include "types.h"
#include <ctime>

enum JsonScalingFormat : uint8_t { SCALED, RAW };

auto build_telemetry_json(const PhocosTelemetry &t, const EepromSettings &settings, std::time_t ts, JsonScalingFormat scaling_format) -> nlohmann::json;
auto build_daily_logs_json(const DailyLogBuffer &logs) -> nlohmann::json;
