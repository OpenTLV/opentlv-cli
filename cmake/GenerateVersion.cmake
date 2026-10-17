# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

include("${CMAKE_CURRENT_LIST_DIR}/Version.cmake")
opentlv_cli_version("${CLI_SOURCE}" OPENTLV_CLI_VERSION)
configure_file("${CLI_SOURCE}/src/version.hpp.in" "${CLI_BINARY}/generated/cli/version.hpp" @ONLY)
file(WRITE "${CLI_BINARY}/cli-version.txt" "${OPENTLV_CLI_VERSION}\n")
