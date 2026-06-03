#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "json.hpp"
#include "eeprom_parser.h"
#include "json_builder.h"
#include "lookups.h"
#include "space_parser.h"
#include "utils.h"

namespace fs = std::filesystem;

int main(int argc, char *argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <logfile.txt> [output.json]\n";
        std::cerr << "  Parses Space telemetry lines from logfile.txt and outputs JSON\n";
        return 1;
    }

    std::string input_file = argv[1];
    std::string output_file = (argc > 2) ? argv[2] : "output.json";

    std::ifstream file(input_file);
    if (!file.is_open()) {
        std::cerr << "Error: cannot open '" << input_file << "'\n";
        return 1;
    }

    DailyLogBuffer daily_logs;
    bool have_eeprom = false;

    std::string line;
    while (std::getline(file, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Try to parse EEPROM line if it starts with '!'
        if (is_eeprom_line(line)) {
            if (parse_eeprom_dump(line)) {
                have_eeprom = true;
            }
            continue;
        }
    }

    file.close();

    if (!have_eeprom) {
        std::cerr << "No EEPROM data found in '" << input_file << "'\n";
        return 1;
    }

    // Build JSON output - only daily logs
    nlohmann::json output = build_daily_logs_json(g_daily_logs);

    // Write JSON to file
    std::ofstream outfile(output_file);
    if (!outfile.is_open()) {
        std::cerr << "Error: cannot open '" << output_file << "' for writing\n";
        return 1;
    }

    outfile << output.dump(2) << "\n";
    outfile.close();

    std::cout << "Successfully parsed " << g_daily_logs.count << " daily log entries\n";
    std::cout << "JSON output written to: " << output_file << "\n";

    return 0;
}
