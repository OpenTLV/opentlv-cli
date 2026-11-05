# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

# Build observations, not another dependency manifest. Evaluate links for the
# selected configuration, including header-only targets absent from link lines.
set(_cli_dependency_report "")
foreach(_cli_target IN ITEMS otlv OpenTLV::tlv++ OpenTLV::tlv nlohmann_json::nlohmann_json)
    get_target_property(_cli_canonical "${_cli_target}" ALIASED_TARGET)
    if(NOT _cli_canonical)
        set(_cli_canonical "${_cli_target}")
    endif()
    string(APPEND _cli_dependency_report
        "${_cli_target}\n${_cli_canonical}\n"
        "$<TARGET_PROPERTY:${_cli_target},SOURCE_DIR>\n"
        "$<TARGET_GENEX_EVAL:${_cli_target},$<TARGET_PROPERTY:${_cli_target},LINK_LIBRARIES>>\n"
        "$<TARGET_GENEX_EVAL:${_cli_target},$<TARGET_PROPERTY:${_cli_target},INTERFACE_LINK_LIBRARIES>>\n")
endforeach()
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/cli-dependencies-$<CONFIG>.txt"
    CONTENT "${_cli_dependency_report}")
