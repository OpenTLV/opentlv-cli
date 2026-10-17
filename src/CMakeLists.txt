# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

set(HEADERS
    bluetooth.hpp
    command.hpp
    command_factory.hpp
    console_color.hpp
    decode.hpp
    diagnostic_collect.hpp
    diagnostic_render.hpp
    diagnostics.hpp
    input.hpp
    json_model.hpp
    options.hpp
    presentation.hpp
    commands/support.hpp
    commands/emv_dictionary.hpp
    commands/help_command.hpp
    commands/version_command.hpp
    commands/formats_command.hpp
    commands/traversal_command.hpp
    commands/dump_command.hpp
    commands/validate_command.hpp
    commands/decode_command.hpp
    commands/query_command.hpp
    commands/diff_command.hpp
    commands/generate_command.hpp
    commands/encode_command.hpp
    commands/tag_command.hpp
    commands/tags_command.hpp
    completion/support.hpp
    completion/completion_option.hpp
    completion/completion_command_spec.hpp
    completion/completion_model.hpp
    completion/shell_completer.hpp
    completion/bash_completer.hpp
    completion/zsh_completer.hpp
    completion/fish_completer.hpp
    completion/powershell_completer.hpp
    completion/completion_command.hpp
)

set(SOURCES
    bluetooth.cpp
    command_factory.cpp
    diagnostic_collect.cpp
    diagnostic_render.cpp
    decode.cpp
    input.cpp
    json_model.cpp
    main.cpp
    options.cpp
    presentation.cpp
    commands/support.cpp
    commands/emv_dictionary.cpp
    commands/help_command.cpp
    commands/version_command.cpp
    commands/formats_command.cpp
    commands/traversal_command.cpp
    commands/dump_command.cpp
    commands/validate_command.cpp
    commands/decode_command.cpp
    commands/query_command.cpp
    commands/diff_command.cpp
    commands/generate_command.cpp
    commands/encode_command.cpp
    commands/tag_command.cpp
    commands/tags_command.cpp
    completion/support.cpp
    completion/completion_option.cpp
    completion/completion_command_spec.cpp
    completion/completion_model.cpp
    completion/bash_completer.cpp
    completion/zsh_completer.cpp
    completion/fish_completer.cpp
    completion/powershell_completer.cpp
    completion/completion_command.cpp
)

add_executable(otlv ${HEADERS} ${SOURCES} core_requirements.cpp)
add_dependencies(otlv cli_version_metadata)
target_include_directories(otlv PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}"
    "${PROJECT_BINARY_DIR}/generated")
target_link_libraries(otlv PRIVATE OpenTLV::tlv++ nlohmann_json::nlohmann_json)
target_compile_features(otlv PRIVATE cxx_std_11)
target_compile_options(otlv PRIVATE
    "$<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>"
)
opentlv_cli_copy_runtime(otlv)

if(UNIX)
    if(APPLE)
        set(_cli_origin "@loader_path")
    else()
        set(_cli_origin "$ORIGIN")
    endif()
    file(RELATIVE_PATH _cli_lib_relative "${CMAKE_INSTALL_FULL_BINDIR}" "${CMAKE_INSTALL_FULL_LIBDIR}")
    set_target_properties(otlv PROPERTIES INSTALL_RPATH "${_cli_origin}/${_cli_lib_relative}")
endif()
install(TARGETS otlv RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
