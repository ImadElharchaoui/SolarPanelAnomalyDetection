#pragma once

#include <charconv>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <fstream>
#include <string>
#include <string_view>
#include <unistd.h>
#include <vector>

inline auto read_file_lines(const std::string &path, std::vector<std::string> &lines) -> bool {
    std::ifstream file(path);
    if (!file.is_open()) {
        std::fprintf(stderr, "[utils] failed to open file: %s\n", path.c_str());
        return false;
    }
    std::string line;
    while (std::getline(file, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        lines.push_back(line);
    }
    return true;
}

inline auto round1(double v) -> double {
    return std::round(v * 10.0) / 10.0;
}

inline auto round2(double v) -> double {
    return std::round(v * 100.0) / 100.0;
}

inline auto mv_to_v(uint32_t mv) -> double {
    return round2(static_cast<double>(mv) / 1000.0);
}

inline auto ma_to_a(uint32_t ma) -> double {
    return round2(static_cast<double>(ma) / 1000.0);
}

inline auto mah_to_ah(uint32_t mah) -> double {
    return round1(static_cast<double>(mah) / 1000.0);
}

inline auto fast_atoi(std::string_view s) -> int {
    if (s.empty()) {
        return 0;
    }
    size_t start = 0;
    bool neg = false;
    if (s[0] == '-') {
        neg = true;
        start = 1;
    } else if (s[0] == '+') {
        start = 1;
    }
    int val = 0;
    auto [ptr, ec] = std::from_chars(s.data() + start, s.data() + s.size(), val);
    if (ec != std::errc{}) {
        return 0;
    }
    return neg ? -val : val;
}

inline auto bcd_to_dec(uint8_t byte) -> uint8_t {
    return static_cast<uint8_t>((((byte >> 4) & 0xF) * 10) + (byte & 0xF));
}

inline auto byte_at(const std::vector<uint8_t> &data, int offset) -> uint8_t {
    if (offset < 0) {
        return 0;
    }
    const auto UOFF = static_cast<std::size_t>(offset);
    return (UOFF < data.size()) ? data[UOFF] : 0;
}

inline auto get_u16(const std::vector<uint8_t> &data, int msb_off, int lsb_off) -> uint16_t {
    return static_cast<uint16_t>((static_cast<uint16_t>(byte_at(data, msb_off)) << 8) |
                                 byte_at(data, lsb_off));
}

inline auto get_u16(const std::vector<uint8_t> &data, int msb_off) -> uint16_t {
    return get_u16(data, msb_off, msb_off + 1);
}

inline void put_u16(std::vector<uint8_t> &bytes, int offset, uint16_t value) {
    if (offset < 0) {
        return;
    }
    const auto UOFF = static_cast<std::size_t>(offset);
    if (UOFF + 1 >= bytes.size()) {
        return;
    }
    bytes[UOFF] = static_cast<uint8_t>((value >> 8) & 0xFF);
    bytes[UOFF + 1] = static_cast<uint8_t>(value & 0xFF);
}

inline auto get_u32(const std::vector<uint8_t> &data, int b0) -> uint32_t {
    return (static_cast<uint32_t>(byte_at(data, b0)) << 24) |
           (static_cast<uint32_t>(byte_at(data, b0 + 1)) << 16) |
           (static_cast<uint32_t>(byte_at(data, b0 + 2)) << 8) |
           static_cast<uint32_t>(byte_at(data, b0 + 3));
}

inline auto current_timestamp() -> std::time_t {
    const std::time_t NOW = std::time(nullptr);
    return NOW;
}

inline auto format_timestamp(std::time_t ts) -> std::string {
    char buf[32];
    std::strftime(buf, sizeof(buf), "%H:%M:%S", std::gmtime(&ts));
    return std::string(buf);
}

inline auto current_timestamp_str() -> std::string {
    return format_timestamp(current_timestamp());
}

inline auto first_non_ws(std::string_view line) -> char {
    const size_t POS = line.find_first_not_of(" \t\r\n");
    return (std::string_view::npos == POS) ? '\0' : line[POS];
}

inline auto is_space_line(std::string_view line) -> bool {
    const char C = first_non_ws(line);
    if (C == '\0' || C == '!' || C == '"' || C == '*' || C == '-') {
        return false;
    }
    return (C >= '0' && C <= '9');
}

inline auto is_eeprom_line(std::string_view line) -> bool {
    return first_non_ws(line) == '!';
}

inline auto parse_hex_dump(std::string_view sv) -> std::vector<uint8_t> {
    std::vector<uint8_t> data;
    data.reserve(1024);

    size_t pos = 0;
    while (pos < sv.size()) {
        size_t semi = sv.find(';', pos);
        if (semi == std::string_view::npos) {
            semi = sv.size();
        }

        const std::string_view FIELD = sv.substr(pos, semi - pos);
        if (FIELD.empty() || FIELD.size() > 3) {
            pos = semi + 1;
            continue;
        }

        bool is_hex = true;
        for (const char C : FIELD) {
            if (std::isxdigit(static_cast<unsigned char>(C)) == 0) {
                is_hex = false;
                break;
            }
        }

        if (is_hex) {
            uint8_t val = 0;
            auto [ptr, ec] = std::from_chars(FIELD.data(), FIELD.data() + FIELD.size(), val, 16);
            if (ec == std::errc{}) {
                data.emplace_back(val);
            }
        }
        pos = semi + 1;
    }
    return data;
}
