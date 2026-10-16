// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_DIAGNOSTIC_RENDER_HPP
#define OPENTLV_CLI_DIAGNOSTIC_RENDER_HPP
#include <string>
#include "tlv++/error.hpp"
#include "tlv++/diagnostic.hpp"
#include "tlv++/reader/reader.hpp"
#include "tlv++/schema/schema.hpp"

// Renders tlv::diagnostic and tlv::validation_issue for otlv's --diagnostics
// option. Kept separate from commands.cpp so this stays easy to lift into
// tlv++ later: everything here operates on the library's own diagnostic
// types, and only the JSON writer (nlohmann) and the symbolic error-name
// table are CLI-specific.

namespace cli {

enum class diagnostic_format { human, compact, json };

// Parses --diagnostics's value ("human", "compact" or "json"); returns false
// for anything else, leaving *out unchanged.
bool parse_diagnostic_format(const char* name, diagnostic_format* out);

// Returns the symbolic name of a result code, e.g. "tlv::errc::schema",
// or "TLV_ERR_UNKNOWN" for a value with no matching case.
const char* error_name(tlv::errc code);

// Renders a base diagnostic: a format/read failure, or one skipped --recover
// range. `stage`, when non-empty (for example "dictionary"), names the layer
// that produced it, distinguishing it from a plain framing/format error.
// `tag_hex`, when non-null, is the affected element's tag as hex text --
// tlv_diagnostic_t itself carries no tag field.
std::string format_diagnostic(const tlv::diagnostic& diagnostic, diagnostic_format format,
                              const char* stage, const char* tag_hex);

// Renders a schema violation, which already carries its own tag, path, field
// name and expected-versus-actual detail computed by
// tlv_schema_validate_all_diag().
std::string format_schema_diagnostic(const tlv::validation_issue& diagnostic,
                                     diagnostic_format            format);

// Renders a reader (wire-level parsing) diagnostic: which step failed, the
// tag being processed if one was already decoded, and, for a value or
// trailer that didn't fit, the declared length versus the bytes available.
std::string format_reader_diagnostic(const tlv::reader_diagnostic& diagnostic,
                                     diagnostic_format             format);

} // namespace cli
#endif
