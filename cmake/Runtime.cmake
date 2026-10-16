# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

# Works for both source and installed Core through the public library target.
function(opentlv_cli_copy_runtime consumer)
    get_target_property(_core_type OpenTLV::tlv TYPE)
    if(WIN32 AND _core_type STREQUAL "SHARED_LIBRARY")
        add_custom_command(TARGET ${consumer} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "$<TARGET_FILE:OpenTLV::tlv>" "$<TARGET_FILE_DIR:${consumer}>"
            VERBATIM)
    endif()
endfunction()
