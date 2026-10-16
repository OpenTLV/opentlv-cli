# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

add_executable(core_c_smoke core_c.c)
target_link_libraries(core_c_smoke PRIVATE OpenTLV::tlv)
add_executable(core_cxx_smoke core_cxx.cpp)
# Includes, language features and the native library are transitive.
target_link_libraries(core_cxx_smoke PRIVATE OpenTLV::tlv++)

get_target_property(_core_type OpenTLV::tlv TYPE)
foreach(_consumer IN ITEMS core_c_smoke core_cxx_smoke)
    if(WIN32 AND _core_type STREQUAL "SHARED_LIBRARY")
        add_custom_command(TARGET ${_consumer} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "$<TARGET_FILE:OpenTLV::tlv>" "$<TARGET_FILE_DIR:${_consumer}>"
            VERBATIM)
    endif()
    add_test(NAME ${_consumer} COMMAND ${_consumer})
endforeach()

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

if(TARGET otlv)
    message(FATAL_ERROR "Core's CLI must not be built by the dependency tests")
endif()
