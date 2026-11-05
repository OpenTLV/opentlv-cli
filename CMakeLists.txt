# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

cmake_minimum_required(VERSION 3.24)
project(OpenTLVCLI LANGUAGES C CXX)

include(cmake/Version.cmake)
opentlv_cli_version("${CMAKE_CURRENT_SOURCE_DIR}" OPENTLV_CLI_VERSION)
configure_file(src/version.hpp.in generated/cli/version.hpp @ONLY)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/cli-version.txt" "${OPENTLV_CLI_VERSION}\n")
message(STATUS "OpenTLV CLI version: ${OPENTLV_CLI_VERSION}")
add_custom_target(cli_version_metadata
    COMMAND "${CMAKE_COMMAND}" "-DCLI_SOURCE=${CMAKE_CURRENT_SOURCE_DIR}"
        "-DCLI_BINARY=${CMAKE_CURRENT_BINARY_DIR}"
        "-DOPENTLV_CLI_CANDIDATE_VERSION=${OPENTLV_CLI_CANDIDATE_VERSION}"
        "-DOPENTLV_CLI_CANDIDATE_SHA=${OPENTLV_CLI_CANDIDATE_SHA}"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/GenerateVersion.cmake"
    VERBATIM)

include(GNUInstallDirs)
include(cmake/Sanitizers.cmake)
include(cmake/Core.cmake)
# Check before creating our executable: embedding Core must provide libraries only.
if(TARGET otlv)
    message(FATAL_ERROR "Core's CLI must not be built by the standalone CLI; use OPENTLV_BUILD_CLI=OFF")
endif()

# CLI-owned C++ targets are ISO C++23 without compiler-specific extensions.
# Set after Core is added so an embedded Core keeps its own language
# requirements; Core's public C++ facade still only requires C++11.
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
include(cmake/Compilers.cmake)
include(cmake/Json.cmake)
add_subdirectory(src)
include(cmake/Dependencies.cmake)

option(OPENTLV_CLI_BUILD_TESTS "Build dependency smoke tests and CLI regression suites" ${PROJECT_IS_TOP_LEVEL})
if(OPENTLV_CLI_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
