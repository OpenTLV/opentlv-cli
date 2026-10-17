# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

cmake_minimum_required(VERSION 3.24)

file(MAKE_DIRECTORY "${WORK_DIR}")
execute_process(COMMAND "${CAPABILITIES}"
    OUTPUT_FILE "${WORK_DIR}/capabilities.cmake"
    ERROR_VARIABLE _capabilities_error RESULT_VARIABLE _capabilities_result)
if(NOT _capabilities_result STREQUAL "0")
    message(FATAL_ERROR "Cannot read public Core capabilities: ${_capabilities_result} ${_capabilities_error}")
endif()
include("${WORK_DIR}/capabilities.cmake")

if(SUITE STREQUAL "integration")
    set(_command "${CMAKE_COMMAND}" "-DCLI=${CLI}")
    foreach(_capability IN ITEMS FIXED BER DER EMV BLUETOOTH_LTV NFC DOCUMENT)
        list(APPEND _command "-DHAS_${_capability}=${HAS_${_capability}}")
    endforeach()
    list(APPEND _command -P "${CMAKE_CURRENT_LIST_DIR}/test.cmake")
elseif(SUITE STREQUAL "examples")
    if(NOT HAS_BER)
        message("SKIP: CLI suite examples requires BER")
        return()
    endif()
    set(_command "${CMAKE_COMMAND}" "-DCLI=${CLI}"
        -P "${CMAKE_CURRENT_LIST_DIR}/examples.cmake")
elseif(SUITE STREQUAL "baseline")
    file(READ "${CLI_VERSION_FILE}" CLI_VERSION)
    string(STRIP "${CLI_VERSION}" CLI_VERSION)
    if(NOT (HAS_BER AND HAS_DER AND HAS_EMV AND HAS_BLUETOOTH_LTV AND
            HAS_NFC AND HAS_QUERY_FRONTEND AND HAS_DOCUMENT))
        message("SKIP: CLI suite baseline requires BER, DER, EMV, Bluetooth, NFC, Query frontend and Document")
        return()
    endif()
    set(_command "${PYTHON}" -B "${CMAKE_CURRENT_LIST_DIR}/check_cli_baseline.py"
        --cli "${CLI}" --version "${CLI_VERSION}" --report "${WORK_DIR}/baseline-report.json")
elseif(SUITE STREQUAL "query")
    if(NOT (HAS_BER AND HAS_QUERY_FRONTEND AND HAS_DOCUMENT))
        message("SKIP: CLI suite query requires BER, Query frontend and Document")
        return()
    endif()
    set(_command "${PYTHON}" "${CMAKE_CURRENT_LIST_DIR}/query/cli_facade.py"
        --cli "${CLI}" --evidence "${WORK_DIR}/query-report.json")
else()
    message(FATAL_ERROR "Unknown CLI test suite: ${SUITE}")
endif()

execute_process(COMMAND ${_command} WORKING_DIRECTORY "${WORK_DIR}"
    RESULT_VARIABLE _suite_result)
if(NOT _suite_result STREQUAL "0")
    message(FATAL_ERROR "CLI suite ${SUITE} failed: ${_suite_result}")
endif()
