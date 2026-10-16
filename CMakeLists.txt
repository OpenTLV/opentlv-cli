# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

cmake_minimum_required(VERSION 3.24)
project(OpenTLVCLI LANGUAGES CXX)

# The migrated CLI retains Core's C++11 baseline.
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Core dependency resolution and the otlv target arrive in issues #2 and #3.
# Do not create a placeholder executable with different command-line behavior.
message(STATUS "OpenTLV CLI bootstrap configured; the otlv executable is not migrated yet.")
