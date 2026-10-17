// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "json_model.hpp"
#include <cstring>
#include <iostream>
#include <nlohmann/json.hpp>
#include "diagnostics.hpp"
#include "tlv/config.h"
#include "tlv++/builtins/asn1/identifier.hpp"

namespace cli {
namespace json_model {

const char* const schema_name = "opentlv.tlv";

} // namespace json_model
} // namespace cli

namespace {

using cli::json_model::document;
using cli::json_model::node;
using json = nlohmann::json;

enum class member {
    none,
    schema,
    version,
    format,
    elements,
    tag,
    value,
    children,
    length_mode,
    annotation
};
enum class scope { root, elements, element };

struct frame {
    scope              kind;
    std::vector<node>* list;    // elements: the array being filled
    node*              element; // element: the object being filled
    unsigned           seen;    // bit per member already present in this object
    member             key;     // member whose value is expected next
    std::string        key_name;
};

int nibble(char ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    return -1;
}

// Strict hexadecimal: complete pairs only, no whitespace, prefix or separators.
bool hex_bytes(const std::string& text, std::vector<uint8_t>& out) {
    if (text.size() % 2) return false;
    out.clear();
    out.reserve(text.size() / 2);
    for (size_t i = 0; i < text.size(); i += 2) {
        const int hi = nibble(text[i]), lo = nibble(text[i + 1]);
        if (hi < 0 || lo < 0) return false;
        out.push_back((uint8_t)(hi * 16 + lo));
    }
    return true;
}

class handler : public json::json_sax_t {
public:
    handler(const char* format, size_t max_depth, size_t max_elements, document& doc)
        : format_(format), max_depth_(max_depth), max_elements_(max_elements), doc_(doc) {}

    // 0 while parsing is healthy; 2 for an invalid document, 3 for a resource limit.
    int         code = 0;
    std::string message;

    bool finished() const {
        return done_;
    }

    bool null() override {
        return wrong_type();
    }
    bool boolean(bool) override {
        return wrong_type();
    }
    bool number_integer(json::number_integer_t) override {
        return wrong_type();
    }
    bool number_float(json::number_float_t, const json::string_t&) override {
        return wrong_type();
    }
    bool binary(json::binary_t&) override {
        return wrong_type();
    }

    bool number_unsigned(json::number_unsigned_t value) override {
        if (!frames_.empty() && frames_.back().kind == scope::root &&
            frames_.back().key == member::version) {
            frames_.back().key = member::none;
            if (value != (json::number_unsigned_t)cli::json_model::schema_version)
                return fail(2, "unsupported JSON schema version " + std::to_string(value) +
                                   "; this otlv reads version " +
                                   std::to_string(cli::json_model::schema_version));
            return true;
        }
        return wrong_type();
    }

    bool string(json::string_t& value) override {
        if (frames_.empty() || frames_.back().kind == scope::elements) return wrong_type();
        frame&       top = frames_.back();
        const member key = top.key;
        top.key = member::none;
        if (top.kind == scope::root) {
            if (key == member::schema) {
                if (value != cli::json_model::schema_name)
                    return fail(2, "unknown schema \"" + value + "\"; expected \"" +
                                       cli::json_model::schema_name + "\"");
                return true;
            }
            if (key == member::format) {
                if (value != format_)
                    return fail(2,
                                "JSON format \"" + value + "\" does not match --format " + format_);
                return true;
            }
            return wrong_type();
        }
        node& element = *top.element;
        switch (key) {
            case member::tag:
                if (!hex_bytes(value, element.tag)) return bad_hex("tag");
                if (element.tag.empty()) return fail(2, "member \"tag\" must not be empty");
                if (element.tag.size() > tlv::asn1::max_tag_size)
                    return fail(2, "tag is longer than the longest tag a supported format accepts");
                return true;
            case member::value:
                if (!hex_bytes(value, element.value)) return bad_hex("value");
                element.has_value = true;
                return true;
            case member::length_mode:
                if (value != "definite" && value != "indefinite")
                    return fail(2, "member \"length_mode\" must be \"definite\" or \"indefinite\"");
                element.has_length_mode = true;
                element.indefinite = value == "indefinite";
                return true;
            case member::annotation: return true; // informational; ignored when encoding
            default: return wrong_type();
        }
    }

    bool start_object(std::size_t) override {
        if (frames_.empty()) {
            frames_.push_back({scope::root, nullptr, nullptr, 0, member::none, ""});
            return true;
        }
        frame& top = frames_.back();
        if (top.kind != scope::elements) return wrong_type();
        if (element_depth_ > max_depth_) return fail(3, "nesting depth limit exceeded");
        if (count_ == max_elements_) return fail(3, "element limit exceeded");
        ++count_;
        top.list->emplace_back();
        frames_.push_back({scope::element, nullptr, &top.list->back(), 0, member::none, ""});
        return true;
    }

    bool key(json::string_t& name) override {
        frame& top = frames_.back();
        member id = member::none;
        if (top.kind == scope::root) {
            if (name == "schema")
                id = member::schema;
            else if (name == "version")
                id = member::version;
            else if (name == "format")
                id = member::format;
            else if (name == "elements")
                id = member::elements;
        } else {
            if (name == "tag")
                id = member::tag;
            else if (name == "value")
                id = member::value;
            else if (name == "children")
                id = member::children;
            else if (name == "length_mode")
                id = member::length_mode;
            else if (name == "name" || name == "description" || name == "decoded" ||
                     name == "decode_error")
                id = member::annotation;
        }
        if (id == member::none)
            return fail(2, "unknown member \"" + name + "\" (lengths are derived when encoding)");
        // Each member, including each annotation name, may appear only once.
        const unsigned bit = id == member::annotation ? 1u << (16 + (name == "name"          ? 0
                                                                     : name == "description" ? 1
                                                                     : name == "decoded"     ? 2
                                                                                             : 3))
                                                      : 1u << (unsigned)id;
        if (top.seen & bit) return fail(2, "duplicate member \"" + name + "\"");
        top.seen |= bit;
        top.key = id;
        top.key_name = name;
        return true;
    }

    bool start_array(std::size_t) override {
        if (frames_.empty()) return wrong_type();
        frame&       top = frames_.back();
        const member key = top.key;
        top.key = member::none;
        if (top.kind == scope::root && key == member::elements) {
            frames_.push_back({scope::elements, &doc_.elements, nullptr, 0, member::none, ""});
            return true;
        }
        if (top.kind == scope::element && key == member::children) {
            top.element->has_children = true;
            std::vector<node>* list = &top.element->children;
            ++element_depth_;
            frames_.push_back({scope::elements, list, top.element, 0, member::none, ""});
            return true;
        }
        return wrong_type();
    }

    bool end_array() override {
        // A "children" array (which records its owner) sits one level deeper.
        if (frames_.back().element) --element_depth_;
        frames_.pop_back();
        return true;
    }

    bool end_object() override {
        frame top = frames_.back();
        frames_.pop_back();
        if (top.kind == scope::root) {
            if (!(top.seen & (1u << (unsigned)member::schema)))
                return fail(2, "missing member \"schema\"");
            if (!(top.seen & (1u << (unsigned)member::version)))
                return fail(2, "missing member \"version\"");
            if (!(top.seen & (1u << (unsigned)member::elements)))
                return fail(2, "missing member \"elements\"");
            done_ = true;
            return true;
        }
        const node& element = *top.element;
        if (!(top.seen & (1u << (unsigned)member::tag))) return fail(2, "element without \"tag\"");
        if (element.has_value == element.has_children)
            return fail(2, "an element needs exactly one of \"value\" (primitive) or "
                           "\"children\" (constructed)");
        if (element.has_length_mode && !element.has_children)
            return fail(2, "\"length_mode\" applies only to constructed elements");
        return true;
    }

    bool parse_error(std::size_t            position, const std::string&,
                     const json::exception& error) override {
        if (!code) {
            code = 2;
            message = "invalid JSON at byte " + std::to_string(position) + ": " + error.what();
        }
        return false;
    }

private:
    bool fail(int rc, const std::string& text) {
        code = rc;
        message = text;
        return false;
    }
    bool wrong_type() {
        std::string name = frames_.empty() ? "" : frames_.back().key_name;
        if (frames_.empty()) return fail(2, "the document must be a JSON object");
        if (frames_.back().kind == scope::elements) return fail(2, "elements must be JSON objects");
        return fail(2, "member \"" + name + "\" has the wrong type");
    }
    bool bad_hex(const char* name) {
        return fail(2, std::string("member \"") + name +
                           "\" must be a string of complete hexadecimal byte pairs");
    }

    std::string        format_;
    size_t             max_depth_;
    size_t             max_elements_;
    size_t             count_ = 0;
    size_t             element_depth_ = 0;
    bool               done_ = false;
    document&          doc_;
    std::vector<frame> frames_;
};

} // namespace

namespace cli {
namespace json_model {

int parse(const std::string& text, const char* format, std::size_t max_depth,
          std::size_t max_elements, document& doc) {
    handler sax(format, max_depth, max_elements, doc);
    // A UTF-8 byte order mark, as written by some Windows editors, is skipped
    // by the parser.
    const bool ok = json::sax_parse(text, &sax);
    if (!ok || sax.code) {
        std::cerr << "otlv: " << (sax.code == 3 ? "" : "invalid JSON document: ")
                  << (sax.message.empty() ? "cannot parse JSON" : sax.message) << "\n";
        return sax.code ? sax.code : 2;
    }
    if (!sax.finished()) return fail(2, "invalid JSON document: incomplete document");
    return 0;
}

} // namespace json_model
} // namespace cli
