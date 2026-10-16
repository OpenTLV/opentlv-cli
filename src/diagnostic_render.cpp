// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "diagnostic_render.hpp"
#include <cstring>
#include <sstream>
#include <nlohmann/json.hpp>

namespace cli {

namespace {

std::string hex_offset(size_t offset) {
    std::ostringstream out;
    out << "0x" << std::hex << std::uppercase << offset;
    return out.str();
}

std::string path_string(const tlv::diagnostic_path& path) {
    // Bound the text from the retained byte identifiers, separators, marker and
    // terminator: even 32 valid long BER tags can exceed a 512-byte buffer.
    size_t capacity = 1 + path.length * 3 + (path.omitted ? 3 : 0);
    for (size_t i = 0; i < path.length; ++i)
        capacity += tlv::path_tag(path, i).as_bytes().size() * 2;
    std::string buffer(capacity, '\0');
    const auto  length = tlv::format_path(path, {&buffer[0], buffer.size()});
    if (!length) return std::string();
    buffer.resize(*length);
    return buffer;
}

std::string hex_tag(tlv::tag tag) {
    const auto        bytes = tag.as_bytes();
    static const char digits[] = "0123456789ABCDEF";
    std::string       result(bytes.size() * 2, '0');
    for (size_t i = 0; i < bytes.size(); ++i) {
        const auto value = static_cast<unsigned>(bytes[i]);
        result[2 * i] = digits[value >> 4];
        result[2 * i + 1] = digits[value & 15];
    }
    return result;
}
const char* form_name(tlv::schema_kind kind) {
    switch (kind) {
        case tlv::schema_kind::primitive: return "primitive";
        case tlv::schema_kind::constructed: return "constructed";
        case tlv::schema_kind::any: return "either";
    }
    return "unknown";
}

// Every diagnostic type shares a base tlv_diagnostic_t (code, severity,
// offset, expected/actual, contexts, path): rendering it once here, rather
// than in each of diagnostic_/schema_/reader_ human/compact/json, is what
// keeps the three formats showing the same fields for every type.

void append_header_human(std::ostringstream& out, const tlv::diagnostic& d) {
    out << tlv::message(tlv::severity_of(d)) << ": " << tlv::message(static_cast<tlv::errc>(d.code))
        << "\n";
    out << "\ncode: " << error_name(static_cast<tlv::errc>(d.code));
    out << "\nlocation: " << tlv::message(tlv::domain(d.location)) << " "
        << tlv::message(tlv::kind(d.location));
    if (d.location.kind)
        out << "\noffset: " << hex_offset(d.location.begin) << " (" << d.location.begin << ")";
    if (tlv::kind(d.location) == tlv::location_kind::span)
        out << "\nrange: " << d.location.begin << ".." << d.location.end;
}

void append_trailer_human(std::ostringstream& out, const tlv::diagnostic& d) {
    if (d.has_path && d.path.omitted) out << "\npath_omitted: " << d.path.omitted;
    if (d.expected) out << "\nexpected: " << d.expected;
    if (d.actual) out << "\nactual: " << d.actual;
    for (const tlv::diagnostic_context* ctx = d.contexts; ctx; ctx = ctx->next)
        out << "\n" << ctx->layer << " " << ctx->key << ": " << ctx->value;
}

std::string trailer_compact(const tlv::diagnostic& d) {
    std::ostringstream out;
    out << "; location=" << tlv::message(tlv::domain(d.location)) << ":"
        << tlv::message(tlv::kind(d.location));
    if (tlv::kind(d.location) == tlv::location_kind::span)
        out << ":" << d.location.begin << ".." << d.location.end;
    if (d.has_path) out << "; path=" << path_string(d.path);
    if (d.has_path && d.path.omitted) out << "; path_omitted=" << d.path.omitted;
    if (d.expected) out << "; expected=" << d.expected;
    if (d.actual) out << "; actual=" << d.actual;
    for (const tlv::diagnostic_context* ctx = d.contexts; ctx; ctx = ctx->next)
        out << "; " << ctx->layer << " " << ctx->key << "=" << ctx->value;
    return out.str();
}

void set_header_json(nlohmann::json& object, const tlv::diagnostic& d) {
    object["severity"] = tlv::message(tlv::severity_of(d));
    object["code"] = error_name(static_cast<tlv::errc>(d.code));
    object["message"] = tlv::message(static_cast<tlv::errc>(d.code));
    object["location"] = {{"domain", tlv::message(tlv::domain(d.location))},
                          {"kind", tlv::message(tlv::kind(d.location))}};
    if (tlv::kind(d.location) != tlv::location_kind::unknown) {
        object["offset"] = d.location.begin;
        object["location"]["begin"] = d.location.begin;
        object["location"]["end"] = d.location.end;
    }
}

void append_trailer_json(nlohmann::json& object, const tlv::diagnostic& d) {
    if (d.expected) object["expected"] = d.expected;
    if (d.actual) object["actual"] = d.actual;
    if (d.contexts) {
        nlohmann::json contexts = nlohmann::json::array();
        for (const tlv::diagnostic_context* ctx = d.contexts; ctx; ctx = ctx->next)
            contexts.push_back({{"layer", ctx->layer}, {"key", ctx->key}, {"value", ctx->value}});
        object["contexts"] = std::move(contexts);
    }
}

// -- Base diagnostic --------------------------------------------------------

std::string diagnostic_human(const tlv::diagnostic& d, const char* stage, const char* tag_hex) {
    std::ostringstream out;
    append_header_human(out, d);
    if (tag_hex) out << "\ntag: " << tag_hex;
    if (d.has_path) out << "\npath: " << path_string(d.path);
    if (stage && *stage) out << "\nstage: " << stage;
    append_trailer_human(out, d);
    return out.str();
}

std::string diagnostic_compact(const tlv::diagnostic& d, const char* stage, const char* tag_hex) {
    std::ostringstream out;
    if (stage && *stage) out << stage << " ";
    out << error_name(static_cast<tlv::errc>(d.code));
    if (d.location.kind)
        out << " at byte " << d.location.begin;
    else
        out << " at unknown location";
    if (tag_hex) out << " tag=" << tag_hex;
    out << ": " << tlv::message(static_cast<tlv::errc>(d.code)) << trailer_compact(d);
    return out.str();
}

std::string diagnostic_json(const tlv::diagnostic& d, const char* stage, const char* tag_hex) {
    nlohmann::json object;
    set_header_json(object, d);
    if (tag_hex) object["tag"] = tag_hex;
    if (d.has_path) {
        object["path"] = path_string(d.path);
        if (d.path.omitted) object["path_omitted"] = d.path.omitted;
    }
    if (stage && *stage) object["stage"] = stage;
    append_trailer_json(object, d);
    return object.dump();
}

// -- Schema diagnostic --------------------------------------------------------

std::string schema_human(const tlv::validation_issue& d) {
    std::ostringstream out;
    append_header_human(out, d.diagnostic());
    out << "\nkind: " << tlv::message(d.kind());
    if (d.error().definition_kind() != tlv::schema_definition_kind::unknown)
        out << "\ndefinition: " << tlv::message(d.error().definition_kind()) << "["
            << d.error().definition().index << "]";
    if (d.depth()) out << "\npath: " << path_string(d.path());
    out << "\ntag: " << hex_tag(d.tag());
    if (d.field()) out << "\nfield: " << d.field();
    if (d.has_length())
        out << "\nexpected length: " << d.expected_length().minimum << ".."
            << d.expected_length().maximum << "\nactual length: " << d.length();
    if (d.has_occurrences())
        out << "\nexpected occurrences: " << d.expected_occurrences().minimum << ".."
            << d.expected_occurrences().maximum << "\nactual occurrences: " << d.occurrences();
    if (d.has_form())
        out << "\nexpected form: " << form_name(d.expected_form())
            << "\nactual form: " << (d.constructed() ? "constructed" : "primitive");
    append_trailer_human(out, d.diagnostic());
    return out.str();
}

std::string schema_compact(const tlv::validation_issue& d) {
    std::ostringstream out;
    out << "schema " << error_name(d.error().status());
    if (tlv::kind(d.diagnostic().location) != tlv::location_kind::unknown)
        out << " at byte " << d.diagnostic().location.begin;
    else
        out << " at unknown location";
    out << " tag=" << hex_tag(d.tag());
    out << ": " << tlv::message(d.error().status()) << trailer_compact(d.diagnostic());
    return out.str();
}

std::string schema_json(const tlv::validation_issue& d) {
    nlohmann::json object;
    set_header_json(object, d.diagnostic());
    object["kind"] = tlv::message(d.kind());
    if (d.error().definition_kind() != tlv::schema_definition_kind::unknown) {
        object["definition_kind"] = tlv::message(d.error().definition_kind());
        object["definition_index"] = d.error().definition().index;
    }
    if (d.depth()) {
        object["path"] = path_string(d.path());
        if (d.path().omitted) object["path_omitted"] = d.path().omitted;
    }
    object["tag"] = hex_tag(d.tag());
    if (d.field()) object["field"] = d.field();
    if (d.has_length()) {
        object["min_length"] = d.expected_length().minimum;
        object["max_length"] = d.expected_length().maximum;
        object["actual_length"] = d.length();
    }
    if (d.has_occurrences()) {
        object["min_occurs"] = d.expected_occurrences().minimum;
        object["max_occurs"] = d.expected_occurrences().maximum;
        object["occurs"] = d.occurrences();
    }
    if (d.has_form()) {
        object["expected_form"] = form_name(d.expected_form());
        object["actual_form"] = d.constructed() ? "constructed" : "primitive";
    }
    append_trailer_json(object, d.diagnostic());
    return object.dump();
}

// -- Reader diagnostic --------------------------------------------------------

std::string reader_human(const tlv::reader_diagnostic& d) {
    std::ostringstream out;
    append_header_human(out, d.diagnostic);
    if (d.diagnostic.has_path) out << "\npath: " << path_string(d.diagnostic.path);
    if (d.detail.has_tag) out << "\ntag: " << hex_tag(tlv::diagnostic_tag(d));
    out << "\nwhile reading: " << tlv::message(tlv::phase(d));
    if (d.detail.has_raw_length) out << "\nraw length: " << hex_tag(tlv::tag(tlv::raw_length(d)));
    if (d.detail.has_declared_length) out << "\ndeclared length: " << d.detail.declared_length;
    if (d.detail.has_available) out << "\navailable: " << d.detail.available;
    append_trailer_human(out, d.diagnostic);
    return out.str();
}

std::string reader_compact(const tlv::reader_diagnostic& d) {
    std::ostringstream out;
    out << error_name(static_cast<tlv::errc>(d.diagnostic.code));
    if (d.diagnostic.location.kind)
        out << " at byte " << d.diagnostic.location.begin;
    else
        out << " at unknown location";
    if (d.detail.has_tag) out << " tag=" << hex_tag(tlv::diagnostic_tag(d));
    out << " while reading " << tlv::message(tlv::phase(d));
    if (d.detail.has_raw_length) out << "; raw_length=" << hex_tag(tlv::tag(tlv::raw_length(d)));
    if (d.detail.has_declared_length) out << "; declared_length=" << d.detail.declared_length;
    if (d.detail.has_available) out << "; available=" << d.detail.available;
    out << ": " << tlv::message(static_cast<tlv::errc>(d.diagnostic.code))
        << trailer_compact(d.diagnostic);
    return out.str();
}

std::string reader_json(const tlv::reader_diagnostic& d) {
    nlohmann::json object;
    set_header_json(object, d.diagnostic);
    if (d.diagnostic.has_path) {
        object["path"] = path_string(d.diagnostic.path);
        if (d.diagnostic.path.omitted) object["path_omitted"] = d.diagnostic.path.omitted;
    }
    if (d.detail.has_tag) object["tag"] = hex_tag(tlv::diagnostic_tag(d));
    object["operation"] = tlv::message(tlv::phase(d));
    if (d.detail.has_raw_length) object["raw_length"] = hex_tag(tlv::tag(tlv::raw_length(d)));
    if (d.detail.has_declared_length) object["declared_length"] = d.detail.declared_length;
    if (d.detail.has_available) object["available"] = d.detail.available;
    if (d.detail.has_required) object["required"] = d.detail.required;
    if (d.detail.has_tag_offset) object["tag_offset"] = d.detail.tag_offset;
    if (d.detail.has_length_offset) object["length_offset"] = d.detail.length_offset;
    if (d.detail.has_value_offset) object["value_offset"] = d.detail.value_offset;
    if (d.detail.has_enclosing_end) object["enclosing_end"] = d.detail.enclosing_end;
    append_trailer_json(object, d.diagnostic);
    return object.dump();
}

} // namespace

bool parse_diagnostic_format(const char* name, diagnostic_format* out) {
    if (!strcmp(name, "human"))
        *out = diagnostic_format::human;
    else if (!strcmp(name, "compact"))
        *out = diagnostic_format::compact;
    else if (!strcmp(name, "json"))
        *out = diagnostic_format::json;
    else
        return false;
    return true;
}

const char* error_name(tlv::errc rc) {
    return tlv::name(rc);
}

std::string format_diagnostic(const tlv::diagnostic& diagnostic, diagnostic_format format,
                              const char* stage, const char* tag_hex) {
    switch (format) {
        case diagnostic_format::human: return diagnostic_human(diagnostic, stage, tag_hex);
        case diagnostic_format::compact: return diagnostic_compact(diagnostic, stage, tag_hex);
        case diagnostic_format::json: return diagnostic_json(diagnostic, stage, tag_hex);
    }
    return std::string();
}

std::string format_schema_diagnostic(const tlv::validation_issue& diagnostic,
                                     diagnostic_format            format) {
    switch (format) {
        case diagnostic_format::human: return schema_human(diagnostic);
        case diagnostic_format::compact: return schema_compact(diagnostic);
        case diagnostic_format::json: return schema_json(diagnostic);
    }
    return std::string();
}

std::string format_reader_diagnostic(const tlv::reader_diagnostic& diagnostic,
                                     diagnostic_format             format) {
    switch (format) {
        case diagnostic_format::human: return reader_human(diagnostic);
        case diagnostic_format::compact: return reader_compact(diagnostic);
        case diagnostic_format::json: return reader_json(diagnostic);
    }
    return std::string();
}

} // namespace cli
