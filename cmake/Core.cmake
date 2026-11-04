# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

include(FetchContent)

# The standalone CLI is an end product with one Core linkage: static. Core's
# own option stays untouched for other consumers; the CLI never offers it.
set(_opentlv_cli_requested_shared "$CACHE{OPENTLV_BUILD_SHARED_LIBS}")
if(_opentlv_cli_requested_shared)
    message(FATAL_ERROR
        "OPENTLV_BUILD_SHARED_LIBS=${_opentlv_cli_requested_shared} is not supported: the standalone "
        "CLI always links OpenTLV Core statically. Remove the option, for an existing build "
        "directory with 'cmake -U OPENTLV_BUILD_SHARED_LIBS', or use a fresh build directory.")
endif()
# A directory-scoped normal variable selects static Core for the embedded
# source build only (Core's option() honors it under CMP0077). The global
# BUILD_SHARED_LIBS and other dependencies are left unchanged.
set(OPENTLV_BUILD_SHARED_LIBS OFF)

set(OPENTLV_CLI_CORE_PACKAGE "" CACHE PATH
    "Explicit Core package configuration directory; disables discovery and Git fallback")

# Core v0.8.0 public targets and CLI regression baseline. Update deliberately
# together with dependency validation; never track a moving branch.
FetchContent_Declare(opentlv_core
    GIT_REPOSITORY https://github.com/OpenTLV/opentlv.git
    GIT_TAG 345c77acb29266036df5f27d04ce315bb61853cc # v0.8.0
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

# Installed packages carry the linkage they were built with; a shared-only
# installation cannot be turned static here and must not be used silently.
get_target_property(_opentlv_cli_core_type OpenTLV::tlv TYPE)
if(NOT _opentlv_cli_core_type STREQUAL "STATIC_LIBRARY")
    message(FATAL_ERROR
        "Selected Core is incompatible: OpenTLV::tlv is a ${_opentlv_cli_core_type}, but the "
        "standalone CLI links Core statically. Install Core with OPENTLV_BUILD_SHARED_LIBS=OFF "
        "and select that package with CMAKE_PREFIX_PATH, or build Core from source with "
        "FETCHCONTENT_SOURCE_DIR_OPENTLV_CORE (or FETCHCONTENT_TRY_FIND_PACKAGE_MODE=NEVER to "
        "skip installed packages).")
endif()
