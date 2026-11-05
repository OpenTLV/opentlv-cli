# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

# Minimum C++ compilers supported by the standalone CLI: the stable toolchains
# its CI validates (docs/development.md). Older compilers that accept C++23 may
# still build the CLI, but they are not supported; warn instead of failing so
# local development is not blocked. Core's compiler requirements are separate.
set(_opentlv_cli_minimum_GNU 15)
set(_opentlv_cli_minimum_Clang 22)
set(_opentlv_cli_minimum_AppleClang 17)
set(_opentlv_cli_minimum_MSVC 19.50)

set(_opentlv_cli_compiler "${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
set(_opentlv_cli_minimum "${_opentlv_cli_minimum_${CMAKE_CXX_COMPILER_ID}}")
if(NOT _opentlv_cli_minimum)
    message(WARNING "${_opentlv_cli_compiler} is not a supported OpenTLV CLI compiler. "
        "Supported: GCC 15+, Clang 22+, AppleClang 17+ or MSVC 19.50+ (Visual Studio 2026).")
elseif(CMAKE_CXX_COMPILER_VERSION VERSION_LESS _opentlv_cli_minimum)
    message(WARNING "${_opentlv_cli_compiler} is older than the supported OpenTLV CLI "
        "minimum ${CMAKE_CXX_COMPILER_ID} ${_opentlv_cli_minimum}; the build is not supported.")
endif()
