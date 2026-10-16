# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

include(FetchContent)

# Core #620 public targets and #621 regression baseline. Update deliberately
# together with dependency validation; never track a moving branch.
FetchContent_Declare(opentlv_core
    GIT_REPOSITORY https://github.com/OpenTLV/opentlv.git
    GIT_TAG edebe957ee2a1e0bf5685c3bd55a33788446e80d
    FIND_PACKAGE_ARGS CONFIG NAMES OpenTLV
)
FetchContent_MakeAvailable(opentlv_core)

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
