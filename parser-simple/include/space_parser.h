#pragma once

#include "types.h"
#include <string_view>

auto parse_phocos_line(std::string_view resp, PhocosTelemetry &out) -> bool;
