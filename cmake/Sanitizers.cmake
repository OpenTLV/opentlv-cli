# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

# Included before Core: instrument the CLI and its static source dependency in
# this directory only, without enabling any Core-owned verification targets.
set(OPENTLV_CLI_SANITIZER "none" CACHE STRING "CLI sanitizer: none, address, address-undefined")
set_property(CACHE OPENTLV_CLI_SANITIZER PROPERTY STRINGS none address address-undefined)
if(OPENTLV_CLI_SANITIZER STREQUAL "none")
    return()
endif()
if(NOT OPENTLV_CLI_SANITIZER MATCHES "^(address|address-undefined)$")
    message(FATAL_ERROR "Unknown OPENTLV_CLI_SANITIZER=${OPENTLV_CLI_SANITIZER}")
endif()

if(MSVC AND CMAKE_CXX_COMPILER_ID STREQUAL "MSVC")
    if(NOT OPENTLV_CLI_SANITIZER STREQUAL "address")
        message(FATAL_ERROR "MSVC supports address only; use OPENTLV_CLI_SANITIZER=address")
    endif()
    # CMake's Debug defaults enable /RTC1 and incremental linking. Keep the
    # override directory-local, including embedded Core, without rewriting cache.
    foreach(_language IN ITEMS C CXX)
        foreach(_suffix IN ITEMS "" _DEBUG _RELEASE _RELWITHDEBINFO _MINSIZEREL)
            string(REGEX REPLACE "/RTC[1csu]+" "" CMAKE_${_language}_FLAGS${_suffix}
                "${CMAKE_${_language}_FLAGS${_suffix}}")
            string(REPLACE "/ZI" "/Zi" CMAKE_${_language}_FLAGS${_suffix}
                "${CMAKE_${_language}_FLAGS${_suffix}}")
        endforeach()
    endforeach()
    # Also handle toolchains using CMake's debug-information abstraction.
    set(CMAKE_MSVC_DEBUG_INFORMATION_FORMAT ProgramDatabase)
    add_compile_options(/fsanitize=address /Zi)
    add_link_options(/INCREMENTAL:NO /DEBUG)
elseif(NOT WIN32 AND CMAKE_C_COMPILER_ID MATCHES "^(GNU|Clang|AppleClang)$"
        AND CMAKE_CXX_COMPILER_ID MATCHES "^(GNU|Clang|AppleClang)$")
    set(_cli_sanitizers address)
    if(OPENTLV_CLI_SANITIZER STREQUAL "address-undefined")
        set(_cli_sanitizers address,undefined)
    endif()
    add_compile_options(-fsanitize=${_cli_sanitizers} -fno-omit-frame-pointer
        -fno-sanitize-recover=all -g)
    add_link_options(-fsanitize=${_cli_sanitizers} -fno-sanitize-recover=all)
else()
    message(FATAL_ERROR "CLI sanitizers require GCC/Clang on Unix or MSVC on Windows")
endif()
