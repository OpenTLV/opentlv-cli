// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "commands/encode_command.hpp"
#include <cstring>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <new>
#include <string>
#include "commands/support.hpp"
#include "commands/validate_command.hpp"
#include "diagnostics.hpp"
#include "input.hpp"
#include "json_model.hpp"
#include "tlv/config.h"
#include "tlv++/builtins/asn1/identifier.hpp"
#include "tlv++/writer/writer.hpp"
#if OPENTLV_FORMAT_BER
#include "tlv++/builtins/asn1/ber.hpp"
#endif
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

using cli::fail;

namespace {

// Builds the element list from --tag/--value.
int specs_from_options(const cli::options& o, std::vector<cli::element_spec>& specs) {
    cli::element_spec spec;
    int               rc = cli::decode_hex(o.tag, tlv::asn1::max_tag_size, spec.tag);
    if (rc == 3) return fail(2, "tag is longer than the longest tag a supported format accepts");
    if (rc) return rc;
    if (spec.tag.empty()) return fail(2, "tag must not be empty");
    if (o.value && (rc = cli::decode_hex(o.value, o.max_input, spec.value))) return rc;
    specs.push_back(std::move(spec));
    return 0;
}

// Views borrow the CLI-owned byte vectors, which outlive each encoding operation.
tlv::bytes byte_view(const std::vector<uint8_t>& bytes) {
    return {reinterpret_cast<const tlv::byte*>(bytes.data()), bytes.size()};
}

tlv::tag make_tag(const std::vector<uint8_t>& bytes) {
    return tlv::tag(byte_view(bytes));
}

std::string hex_text(const std::vector<uint8_t>& bytes) {
    static const char digits[] = "0123456789ABCDEF";
    std::string       text;
    text.reserve(bytes.size() * 2);
    for (uint8_t byte : bytes) {
        text += digits[byte >> 4];
        text += digits[byte & 0xF];
    }
    return text;
}

// Reports a writer rejection with the offending element's tag.
int write_failed(std::size_t index, tlv::errc rc) {
    std::cerr << "otlv: cannot encode element " << index << ": " << tlv::message(rc) << "\n";
    return rc == tlv::errc::out_of_memory ? 3 : 1;
}

// Encodes the elements of a JSON document with the format's writer. Children
// are encoded first and become their parent's value, so every length is
// derived from the bytes actually written.
class json_encoder {
public:
    json_encoder(tlv::format format, const char* name) : format_(format), name_(name) {
#if OPENTLV_FORMAT_BER
        ber_ = !strcmp(name, "ber");
#endif
    }

    int encode(const std::vector<cli::json_model::node>& elements, std::vector<uint8_t>& out) {
        for (const cli::json_model::node& element : elements) {
            const int rc = encode_element(element, out);
            if (rc) return rc;
        }
        return 0;
    }

private:
    bool is_constructed(tlv::tag tag) const {
        return format_.is_constructed(tag);
    }

    int reject(std::size_t index, const std::string& reason) {
        std::cerr << "otlv: cannot encode element " << index << ": " << reason << "\n";
        return 2;
    }

    // Elements are numbered in preorder, as they appear in the document.
    int encode_element(const cli::json_model::node& element, std::vector<uint8_t>& out) {
        const std::size_t           index = index_++;
        const tlv::tag              tag = make_tag(element.tag);
        std::vector<uint8_t>        children;
        const std::vector<uint8_t>* value = &element.value;

        if (format_.has_constructed_classifier()) {
            const bool constructed = is_constructed(tag);
            if (element.has_children && !constructed)
                return reject(index, "tag " + hex_text(element.tag) +
                                         " is primitive; use \"value\" instead of \"children\"");
            if (element.has_value && constructed)
                return reject(index, "tag " + hex_text(element.tag) +
                                         " is constructed; use \"children\" instead of \"value\"");
        } else if (element.has_children) {
            return reject(index, std::string("format ") + name_ +
                                     " has no constructed elements; use \"value\"");
        }
        if (element.indefinite && !ber_)
            return reject(index,
                          std::string("indefinite length requires format ber, not ") + name_);
        if (element.has_children) {
            const int rc = encode(element.children, children);
            if (rc) return rc;
            value = &children;
        }
        const std::size_t before = out.size();
        tlv::format       encoding_format = format_;
#if OPENTLV_FORMAT_BER
        if (element.indefinite) encoding_format = tlv::ber::indefinite_format{};
#endif
        auto measured = tlv::encoded_size(tag, value->size(), encoding_format);
        if (!measured) return write_failed(index, measured.error().status());
        const size_t size = *measured;
        if (size > SIZE_MAX - before) return fail(3, "encoded output too large");
        try {
            out.resize(before + size);
        } catch (const std::bad_alloc&) {
            return fail(3, "cannot allocate CLI memory");
        }
        auto* destination = reinterpret_cast<tlv::byte*>(out.data() + before);
#if OPENTLV_FORMAT_BER
        if (element.indefinite) {
            auto written = tlv::ber::write_indefinite({destination, size}, tag, byte_view(*value));
            return written ? 0 : write_failed(index, written.error().status());
        }
#endif
        tlv::writer<> writer(destination, size, format_);
        auto          written = writer.write(tag, *value);
        return written ? 0 : write_failed(index, written.error().status());
    }

    tlv::format format_;
    const char* name_;
    bool        ber_ = false;
    std::size_t index_ = 0;
};

// Emits encoded bytes as hex text or raw bytes, to stdout or --output-file.
int emit(const cli::options& o, const std::vector<uint8_t>& out) {
    if (o.output_file) {
        std::ofstream file(o.output_file, std::ios::binary | std::ios::trunc);
        if (!file) return fail(3, "cannot open output file");
        if (o.binary_output)
            file.write(reinterpret_cast<const char*>(out.data()), (std::streamsize)out.size());
        else
            file << hex_text(out) << "\n";
        file.flush();
        if (!file) return fail(3, "cannot write output file");
        file.close();
        return file ? 0 : fail(3, "cannot write output file");
    }
    if (o.binary_output) {
#ifdef _WIN32
        if (_setmode(_fileno(stdout), _O_BINARY) == -1)
            return fail(3, "cannot set binary stdout mode");
#endif
        std::cout.write(reinterpret_cast<const char*>(out.data()), (std::streamsize)out.size());
    } else {
        std::cout << hex_text(out) << "\n";
    }
    return cli::flush_stdout();
}

// Encodes the JSON document named by --input.
int encode_json(const cli::options& o, tlv::format format) {
    std::string               text;
    cli::json_model::document document;
    std::vector<uint8_t>      out;
    int                       rc;

    if ((rc = cli::read_text(o.input, o.max_input, text))) return rc;
    if ((rc = cli::json_model::parse(text, o.format, o.max_depth, o.max_elements, document)))
        return rc;
    try {
        json_encoder encoder(format, o.format);
        if ((rc = encoder.encode(document.elements, out))) return rc;
    } catch (const std::bad_alloc&) {
        return fail(3, "cannot allocate CLI memory");
    }
    if (out.size() > o.max_input) return fail(3, "encoded output exceeds --max-input-size");

    // The output must be accepted by the reader and structural validator
    // validate_command uses for this format, under the same limits.
    cli::options check;
    check.command = "validate";
    check.format = o.format;
    check.max_input = o.max_input;
    check.max_depth = o.max_depth;
    check.max_elements = o.max_elements;
    check.fixed_tag_size = o.fixed_tag_size;
    check.fixed_length_size = o.fixed_length_size;
    check.fixed_byte_order = o.fixed_byte_order;
    cli::validate_command validation(check, out);
    if (validation.run() != 0) return fail(1, "encoded output failed validation");
    return emit(o, out);
}

} // namespace

namespace cli {

int encode_command::run() {
    const options&            o = options_;
    format_selection          selection(o);
    auto                      format = selection.get();
    std::vector<element_spec> specs;
    std::vector<uint8_t>      out;
    std::size_t               total = 0, i;
    int                       rc;

    if (!format) return fail(2, "unknown or disabled format; use otlv formats");
    if (!format->writable())
        return fail(2, (std::string("format ") + o.format + " does not support encoding").c_str());
    if (o.input) return encode_json(o, *format);
    if ((rc = specs_from_options(o, specs))) return rc;

    // Validate every element and size the whole output before writing, so a
    // rejected element never yields partial output.
    for (i = 0; i < specs.size(); ++i) {
        auto size = tlv::encoded_size(make_tag(specs[i].tag), specs[i].value.size(), *format);
        if (!size) return write_failed(i, size.error().status());
        if (total > SIZE_MAX - *size) return fail(3, "encoded output too large");
        total += *size;
    }
    try {
        out.resize(total);
    } catch (const std::bad_alloc&) {
        return fail(3, "cannot allocate CLI memory");
    }
    tlv::writer<> writer(reinterpret_cast<tlv::byte*>(out.data()), out.size(), *format);
    for (i = 0; i < specs.size(); ++i) {
        auto written = writer.write(make_tag(specs[i].tag), specs[i].value);
        if (!written) return write_failed(i, written.error().status());
    }
    return emit(o, out);
}

} // namespace cli
