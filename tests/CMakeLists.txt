# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

add_executable(core_c_smoke core_c.c)
target_link_libraries(core_c_smoke PRIVATE OpenTLV::tlv)
add_executable(core_cxx_smoke core_cxx.cpp)
# Includes, language features and the native library are transitive.
target_link_libraries(core_cxx_smoke PRIVATE OpenTLV::tlv++)

add_executable(core_capabilities core_capabilities.c)
target_link_libraries(core_capabilities PRIVATE OpenTLV::tlv)
foreach(_consumer IN ITEMS core_c_smoke core_cxx_smoke core_capabilities)
    opentlv_cli_copy_runtime(${_consumer})
endforeach()
add_test(NAME core_c_smoke COMMAND core_c_smoke)
add_test(NAME core_cxx_smoke COMMAND core_cxx_smoke)

# Evidence used by the external dependency integration runner.
get_target_property(_core_imported OpenTLV::tlv IMPORTED)
if(_core_imported)
    set(_core_mode package)
else()
    set(_core_mode source)
endif()
get_target_property(_core_c_source OpenTLV::tlv SOURCE_DIR)
get_target_property(_core_cxx_source OpenTLV::tlv++ SOURCE_DIR)
get_target_property(_core_cxx_imported OpenTLV::tlv++ IMPORTED)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/core-selection.txt"
    "${_core_mode}\n${opentlv_core_SOURCE_DIR}\n"
    "${_core_c_source}\n${_core_cxx_source}\n${_core_cxx_imported}\n")

# Read capabilities from the public headers used to build the executable. This
# works for source and installed Core packages without private CMake variables.
find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
add_test(NAME cli_version COMMAND ${Python3_EXECUTABLE} -B
    "${CMAKE_CURRENT_SOURCE_DIR}/check_version.py" "$<TARGET_FILE:otlv>" "${PROJECT_BINARY_DIR}/cli-version.txt")
add_test(NAME cli_version_contract COMMAND ${Python3_EXECUTABLE} -B
    "${CMAKE_CURRENT_SOURCE_DIR}/test_version.py")
add_test(NAME cli_release_gate COMMAND ${Python3_EXECUTABLE} -B
    "${CMAKE_CURRENT_SOURCE_DIR}/test_release.py")
add_test(NAME Integration_cli_migration
    COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/check_migration.py")
set_tests_properties(Integration_cli_migration PROPERTIES LABELS "integration;cli")
function(add_cli_suite name suite)
    set(_work_dir "${CMAKE_CURRENT_BINARY_DIR}/${name}-$<CONFIG>")
    add_test(NAME ${name} COMMAND ${CMAKE_COMMAND}
        "-DCLI=$<TARGET_FILE:otlv>"
        "-DCAPABILITIES=$<TARGET_FILE:core_capabilities>"
        "-DPYTHON=${Python3_EXECUTABLE}"
        "-DSUITE=${suite}"
        "-DWORK_DIR=${_work_dir}"
        "-DCLI_VERSION_FILE=${PROJECT_BINARY_DIR}/cli-version.txt"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/run_cli_suite.cmake")
    set_tests_properties(${name} PROPERTIES LABELS "integration;cli"
        SKIP_REGULAR_EXPRESSION "SKIP: CLI suite")
endfunction()

add_cli_suite(Integration_cli integration)
add_cli_suite(Integration_cli_cpp_examples examples)
set_tests_properties(Integration_cli_cpp_examples PROPERTIES LABELS "integration;cli;examples")
add_test(NAME Integration_cli_baseline_runner
    COMMAND ${Python3_EXECUTABLE} -B "${CMAKE_CURRENT_SOURCE_DIR}/baseline/test_runner.py")
set_tests_properties(Integration_cli_baseline_runner PROPERTIES LABELS "integration;cli")
add_cli_suite(Integration_cli_baseline baseline)
set_tests_properties(Integration_cli_baseline PROPERTIES TIMEOUT 300)
add_cli_suite(query-cli-conformance query)
set_tests_properties(query-cli-conformance PROPERTIES LABELS "query;conformance;memcheck-full"
    TIMEOUT 3600)
