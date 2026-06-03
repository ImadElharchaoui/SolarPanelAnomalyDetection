cmake_minimum_required(VERSION 3.15)
project(solar_parser)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Enable FetchContent to download nlohmann/json
include(FetchContent)

FetchContent_Declare(json
  URL https://github.com/nlohmann/json/releases/download/v3.11.2/json.hpp
  DOWNLOAD_NO_EXTRACT TRUE
)

FetchContent_MakeAvailable(json)

# Create include directory for json.hpp
add_library(nlohmann_json INTERFACE)
target_include_directories(nlohmann_json INTERFACE ${json_SOURCE_DIR})

# Source files
set(SOURCES
  src/main.cpp
  src/space_parser.cpp
  src/json_builder.cpp
  src/eeprom_parser.cpp
)

# Create executable
add_executable(mppt_parser ${SOURCES})

# Include directories
target_include_directories(mppt_parser PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)

# Link nlohmann_json library
target_link_libraries(mppt_parser PRIVATE nlohmann_json)

# Compiler flags
if(MSVC)
  target_compile_options(mppt_parser PRIVATE /W4)
else()
  target_compile_options(mppt_parser PRIVATE -Wall -Wextra -Werror)
endif()
