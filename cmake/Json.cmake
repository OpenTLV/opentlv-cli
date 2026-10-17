# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

# Keep the originating CLI JSON version. Core remains free of this dependency.
include(FetchContent)
FetchContent_Declare(nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG 9cca280a4d0ccf0c08f47a99aa71d1b0e52f8d03 # v3.11.3
    FIND_PACKAGE_ARGS 3.11.3 EXACT CONFIG
)
FetchContent_MakeAvailable(nlohmann_json)
