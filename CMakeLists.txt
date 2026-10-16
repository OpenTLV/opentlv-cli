# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

cmake_minimum_required(VERSION 3.24)
project(OpenTLVCLI LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(cmake/Core.cmake)

option(OPENTLV_CLI_BUILD_TESTS "Build Core dependency integration smoke tests" ${PROJECT_IS_TOP_LEVEL})
if(OPENTLV_CLI_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# The real otlv executable is migrated in issue #3.
message(STATUS "OpenTLV CLI Core integration configured; otlv is not migrated yet.")
