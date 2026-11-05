# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

# Configuration-specific observations from the actual selected public targets.
# JSON escaping happens before generator-expression evaluation; paths emitted by
# CMake use forward slashes. Lists remain semicolon-delimited JSON strings.
set(_cli_metadata "{}")
macro(cli_metadata key value)
    set(_cli_value "${value}")
    string(REPLACE "\\" "\\\\" _cli_value "${_cli_value}")
    string(REPLACE "\"" "\\\"" _cli_value "${_cli_value}")
    string(REPLACE "\n" "\\n" _cli_value "${_cli_value}")
    string(REPLACE "\r" "\\r" _cli_value "${_cli_value}")
    string(REPLACE "\t" "\\t" _cli_value "${_cli_value}")
    string(JSON _cli_metadata SET "${_cli_metadata}" "${key}" "\"${_cli_value}\"")
endmacro()
cli_metadata(configuration "$<CONFIG>")
cli_metadata(source "${PROJECT_SOURCE_DIR}")
cli_metadata(core_source "${opentlv_core_SOURCE_DIR}")
cli_metadata(json_source "${nlohmann_json_SOURCE_DIR}")
cli_metadata(json_imported "$<TARGET_PROPERTY:nlohmann_json::nlohmann_json,IMPORTED>")
cli_metadata(core_imported "${_opentlv_cli_core_imported}")
cli_metadata(core_library "$<TARGET_FILE:OpenTLV::tlv>")
cli_metadata(core_type "$<TARGET_PROPERTY:OpenTLV::tlv,TYPE>")
cli_metadata(core_includes "$<TARGET_PROPERTY:OpenTLV::tlv,INTERFACE_INCLUDE_DIRECTORIES>;$<TARGET_PROPERTY:OpenTLV::tlv++,INTERFACE_INCLUDE_DIRECTORIES>")
cli_metadata(json_includes "$<TARGET_PROPERTY:nlohmann_json::nlohmann_json,INTERFACE_INCLUDE_DIRECTORIES>")
cli_metadata(executable "$<TARGET_FILE:otlv>")
foreach(_cli_key IN ITEMS CMAKE_VERSION CMAKE_MAKE_PROGRAM CMAKE_GENERATOR CMAKE_GENERATOR_PLATFORM
        CMAKE_GENERATOR_TOOLSET CMAKE_SYSTEM_NAME CMAKE_SYSTEM_VERSION CMAKE_SYSTEM_PROCESSOR
        CMAKE_SIZEOF_VOID_P CMAKE_CROSSCOMPILING CMAKE_C_COMPILER CMAKE_C_COMPILER_ID
        CMAKE_C_COMPILER_VERSION CMAKE_C_COMPILER_TARGET CMAKE_CXX_COMPILER
        CMAKE_CXX_COMPILER_ID CMAKE_CXX_COMPILER_VERSION CMAKE_CXX_COMPILER_TARGET
        CMAKE_C_COMPILER_ARCHITECTURE_ID CMAKE_CXX_COMPILER_ARCHITECTURE_ID
        CMAKE_CXX_STANDARD CMAKE_CXX_EXTENSIONS CMAKE_MSVC_RUNTIME_LIBRARY
        CMAKE_SYSROOT CMAKE_OSX_SYSROOT CMAKE_OSX_ARCHITECTURES CMAKE_OSX_DEPLOYMENT_TARGET
        CMAKE_TOOLCHAIN_FILE OPENTLV_CLI_SANITIZER)
    cli_metadata("${_cli_key}" "${${_cli_key}}")
endforeach()
cli_metadata(CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION "${CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION}")
cli_metadata(CMAKE_LINKER "${CMAKE_LINKER}")
cli_metadata(CMAKE_AR "${CMAKE_AR}")
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/cli-build-inputs-$<CONFIG>.json"
    CONTENT "${_cli_metadata}\n" TARGET otlv)

find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
add_custom_target(cli_build_metadata ALL
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/scripts/build_metadata.py"
        --build "${PROJECT_BINARY_DIR}" --configuration "$<CONFIG>"
    DEPENDS otlv
    COMMENT "Recording CLI build provenance and runtime imports"
    VERBATIM)
