// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

// The CLI is compiled as ISO C++23 without compiler-specific language
// extensions. Reject builds that select an older standard or a GNU dialect,
// for example through CMAKE_CXX_FLAGS. MSVC reports the selected standard in
// _MSVC_LANG; its __cplusplus stays 199711L unless /Zc:__cplusplus is given.
#if defined(_MSVC_LANG)
#define OPENTLV_CLI_CXX_STANDARD _MSVC_LANG
#else
#define OPENTLV_CLI_CXX_STANDARD __cplusplus
#endif

static_assert(OPENTLV_CLI_CXX_STANDARD > 202002L, "OpenTLV CLI requires C++23 or newer");

#if defined(__GNUC__) && !defined(__STRICT_ANSI__)
#error "OpenTLV CLI requires ISO C++ without GNU extensions (CMAKE_CXX_EXTENSIONS=OFF)"
#endif
