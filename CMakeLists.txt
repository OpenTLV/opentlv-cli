# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

cmake_minimum_required(VERSION 3.24)
project(OpenTLVCLI LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(GNUInstallDirs)
include(cmake/Core.cmake)
# Check before creating our executable: embedding Core must provide libraries only.
if(TARGET otlv)
    message(FATAL_ERROR "Core's CLI must not be built by the standalone CLI; use OPENTLV_BUILD_CLI=OFF")
endif()
include(cmake/Json.cmake)
include(cmake/Runtime.cmake)
add_subdirectory(src)

option(OPENTLV_CLI_BUILD_TESTS "Build dependency smoke tests and CLI regression suites" ${PROJECT_IS_TOP_LEVEL})
if(OPENTLV_CLI_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
