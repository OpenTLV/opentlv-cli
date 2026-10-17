// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_SUPPORT_HPP
#define OPENTLV_CLI_COMMANDS_SUPPORT_HPP
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
#include "decode.hpp"
#include "diagnostic_render.hpp"
#include "options.hpp"
#include "presentation.hpp"
#include "tlv++/types.hpp"
#include "tlv++/visitor.hpp"
#include "tlv++/formats/runtime_fixed.hpp"
#include "tlv++/reader/tree.hpp"

// Small utilities shared by more than one file under commands/, kept out of
// any single command's own file so none of them has to include another
// command's internals just to reuse a formatting helper.

namespace cli {

// A byte range --recover skipped, and the first error that made it unreadable.
// The diagnostic's location, in input coordinates, is the only failure position.
struct skipped_range {
    tlv::reader_diagnostic diagnostic{};
    std::size_t            offset;
    std::size_t            length;
    tlv::errc              error;
};

bool is_json(const options& o);

// Owns runtime Fixed configuration; returned views borrow this owner. Built-in
// views borrow immutable program-lifetime descriptors. No shared mutable state.
class format_selection {
public:
    explicit format_selection(const options& o);
    format_selection(const format_selection&) = delete;
    format_selection&                      operator=(const format_selection&) = delete;
    tlv::expected<tlv::format, tlv::error> get() const;

private:
    const char*               name_;
    tlv::runtime_fixed_format fixed_;
};

// Prints `length` bytes as uppercase hex ("0A1B..."), restoring std::cout's
// prior formatting state afterward so callers can freely mix this with
// ordinary decimal output.
void print_hex(const uint8_t* data, std::size_t length);
void print_hex(tlv::bytes bytes);

// Prints a tag's bytes as hex, wrapped in the CLI's tag accent color when
// enabled. Shared by dump's element output and --pdol.
void print_tag(tlv::tag tag, bool color);

// Same encoding as print_hex, built as a string instead of streamed, for
// --output json's field values (which are never color-wrapped).
std::string hex_string(const uint8_t* data, std::size_t length);
std::string hex_string(tlv::bytes bytes);

// What every traversal of the input needs to know about the selected format.
using tree_visitor = tlv::visit_control (*)(const tlv::element_view*, size_t, size_t, void*);

struct traversal_env {
    const cli::options* options;
    const tlv::format*  format;
    bool                is_der;
};

// Traverses `slice_size` bytes of `slice`, which starts at absolute offset `base`
// of the input, allowing at most `max_elements` elements. On failure the
// optional *diagnostic receives the failure with its location in input coordinates.
tlv::errc visit_slice(const traversal_env& env, const uint8_t* slice, std::size_t slice_size,
                      std::size_t base, std::size_t max_elements, tree_visitor visitor,
                      void* context, tlv::reader_diagnostic* diagnostic = nullptr);

// Compact text for a location: "input:point:3", "input:span:3..5" or "unknown:unknown".
std::string location_text(const tlv::location& location);

// Adds the "name" and, if requested, "description" EMV dictionary fields to
// a JSON element object, from the same lookup the text renderer uses. A tag
// unknown in its context is labelled only when `label_unknown`; the decode
// document leaves it unnamed.
template <class Json>
void json_emv(Json& object, const cli_presentation_t& presentation,
              const tlv::element_view* element, std::size_t depth, int describe,
              bool label_unknown = true) {
    const cli_emv_info info = cli_presentation_emv_info(&presentation, element, depth, describe);
    if (info.known)
        object["name"] = info.name;
    else if (label_unknown)
        object["name"] = "Unknown EMV tag in this context";
    if (info.has_description) object["description"] = info.description;
}

// Adds the "decoded" or "decode_error" field to a JSON element object, or
// neither for a tag/value kind with no codec.
template <class Json>
void json_decode(Json& object, const cli_presentation_t& presentation,
                 const tlv::element_view* element, std::size_t depth) {
    const decode_result result = decode_emv_value(presentation.contexts[depth], element);
    if (result.status == decode_status::ok)
        object["decoded"] = result.text;
    else if (result.status == decode_status::error)
        object["decode_error"] = result.text;
}

// A location object: domain and kind, plus begin and end when known.
template <class Json> Json location_json(const tlv::location& location) {
    Json object;
    object["domain"] = tlv::message(tlv::domain(location));
    object["kind"] = tlv::message(tlv::kind(location));
    if (tlv::kind(location) != tlv::location_kind::unknown) {
        object["begin"] = location.begin;
        object["end"] = location.end;
    }
    return object;
}

// The "skipped" array shared by dump's and decode's JSON documents.
template <class Json> Json skipped_json(const std::vector<skipped_range>& skipped) {
    Json array = Json::array();
    for (const skipped_range& range : skipped) {
        Json object;
        object["offset"] = range.offset;
        object["length"] = range.length;
        object["error"] = error_name(range.error);
        object["location"] = location_json<Json>(range.diagnostic.diagnostic.location);
        object["message"] = tlv::message(range.error);
        array.push_back(std::move(object));
    }
    return array;
}

} // namespace cli
#endif
