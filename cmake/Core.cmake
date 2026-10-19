# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

include(FetchContent)
set(OPENTLV_CLI_CORE_PACKAGE "" CACHE PATH
    "Explicit Core package configuration directory; disables discovery and Git fallback")

# Core #620 public targets and #621 regression baseline. Update deliberately
# together with dependency validation; never track a moving branch.
FetchContent_Declare(opentlv_core
    GIT_REPOSITORY https://github.com/OpenTLV/opentlv.git
    GIT_TAG edebe957ee2a1e0bf5685c3bd55a33788446e80d
    FIND_PACKAGE_ARGS CONFIG NAMES OpenTLV
)
if(OPENTLV_CLI_CORE_PACKAGE)
    # The CI verifier supplies this only after authenticating the exact package.
    # A missing/incompatible package must not silently select another dependency.
    if(FETCHCONTENT_SOURCE_DIR_OPENTLV_CORE)
        message(FATAL_ERROR "Explicit Core package and source override cannot be combined")
    endif()
    if(NOT EXISTS "${OPENTLV_CLI_CORE_PACKAGE}/OpenTLVConfig.cmake")
        message(FATAL_ERROR "Selected Core package is missing OpenTLVConfig.cmake")
    endif()
    set(OpenTLV_DIR "${OPENTLV_CLI_CORE_PACKAGE}")
    find_package(OpenTLV CONFIG REQUIRED PATHS "${OPENTLV_CLI_CORE_PACKAGE}" NO_DEFAULT_PATH)
else()
    FetchContent_MakeAvailable(opentlv_core)
endif()

# Numeric Core versions alone cannot distinguish the old installed tlvpp
# target from the public integration introduced after the 0.7.1 release.
foreach(_opentlv_cli_target IN ITEMS OpenTLV::tlv OpenTLV::tlv++)
    if(NOT TARGET ${_opentlv_cli_target})
        message(FATAL_ERROR
            "Selected Core is incompatible: missing ${_opentlv_cli_target}. "
            "Use Core with the public CMake integration from Core #620 and "
            "OPENTLV_BUILD_CXX=ON. Select it with "
            "FETCHCONTENT_SOURCE_DIR_OPENTLV_CORE or CMAKE_PREFIX_PATH.")
    endif()
endforeach()
