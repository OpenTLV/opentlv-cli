// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include <vector>
#include <algorithm>
#include "commands/support.hpp"
#include <cstring>
#include <iomanip>
#include <ios>
#include <iostream>
#include "console_color.hpp"
#include "tlv/config.h"
#if OPENTLV_NFC
#include "tlv++/builtins/nfc/type2.hpp"
#endif
#if OPENTLV_EMV
#include "tlv++/builtins/emv/format.hpp"
#endif
#if OPENTLV_BLUETOOTH
#include "tlv++/builtins/bluetooth/ltv.hpp"
#endif
#if OPENTLV_FORMAT_BER
#include "tlv++/builtins/asn1/ber.hpp"
#endif
#if OPENTLV_FORMAT_DER
#include "tlv++/builtins/asn1/der.hpp"
#endif

namespace cli {

bool is_json(const options& o) {
    return !strcmp(o.output, "json");
}

format_selection::format_selection(const options& o)
    : name_(o.format), fixed_(o.fixed_tag_size, o.fixed_length_size,
                              !strcmp(o.fixed_byte_order, "little") ? tlv::byte_order::little_endian
                                                                    : tlv::byte_order::big_endian) {
}

tlv::expected<tlv::format, tlv::error> format_selection::get() const {
    if (name_) {
        if (!strcmp(name_, "fixed")) return fixed_.view();
#if OPENTLV_EMV
        if (!strcmp(name_, "emv")) return tlv::emv::format{};
#endif
#if OPENTLV_FORMAT_BER
        if (!strcmp(name_, "ber")) return tlv::ber::format{};
#endif
#if OPENTLV_FORMAT_DER
        if (!strcmp(name_, "der")) return tlv::der::format{};
#endif
#if OPENTLV_BLUETOOTH
        if (!strcmp(name_, "bluetooth-ltv")) return tlv::bluetooth::format{};
#endif
#if OPENTLV_NFC
        if (!strcmp(name_, "nfc-type2")) return tlv::nfc::format{};
#endif
    }
    return tlv::unexpected<tlv::error>(tlv::error(tlv::errc::invalid_argument));
}

void print_hex(const uint8_t* data, std::size_t length) {
    const std::ios::fmtflags saved = std::cout.flags();
    const char               fill = std::cout.fill('0');
    std::cout << std::hex << std::uppercase;
    for (std::size_t i = 0; i < length; ++i) std::cout << std::setw(2) << (unsigned)data[i];
    std::cout.fill(fill);
    std::cout.flags(saved);
}

void print_hex(tlv::bytes bytes) {
    print_hex(reinterpret_cast<const uint8_t*>(bytes.data()), bytes.size());
}

void print_tag(tlv::tag tag, bool color) {
    console_color scope(std::cout, color);
    print_hex(tag.as_bytes());
}

std::string location_text(const tlv::location& location) {
    std::string text =
        std::string(tlv::message(tlv::domain(location))) + ":" + tlv::message(tlv::kind(location));
    if (tlv::kind(location) == tlv::location_kind::unknown) return text;
    text += ":" + std::to_string(location.begin);
    if (tlv::kind(location) == tlv::location_kind::span)
        text += ".." + std::to_string(location.end);
    return text;
}

std::string hex_string(tlv::bytes bytes) {
    return hex_string(reinterpret_cast<const uint8_t*>(bytes.data()), bytes.size());
}

std::string hex_string(const uint8_t* data, std::size_t length) {
    static const char digits[] = "0123456789ABCDEF";
    std::string       result(length * 2, '0');
    for (std::size_t i = 0; i < length; ++i) {
        result[i * 2] = digits[data[i] >> 4];
        result[i * 2 + 1] = digits[data[i] & 0xF];
    }
    return result;
}

tlv::errc visit_slice(const traversal_env& env, const uint8_t* slice, std::size_t slice_size,
                      std::size_t base, std::size_t max_elements, tree_visitor visitor,
                      void* context, tlv::reader_diagnostic* diagnostic) {
    const options& o = *env.options;
    tlv::errc      result;
#if OPENTLV_FORMAT_DER
    if (env.is_der) {
        tlv::der::limits limits = {o.max_depth, o.max_input, o.max_input, max_elements};
        const auto       status =
            tlv::der::visit({reinterpret_cast<const tlv::byte*>(slice), slice_size}, limits,
                            [&](const tlv::element_view& element, size_t depth, size_t offset) {
                                return visitor ? visitor(&element, depth, offset, context)
                                               : tlv::visit_control::next;
                            });
        result = status ? tlv::errc::ok : status.error().status();
        if (!status && diagnostic) {
            diagnostic->diagnostic = tlv::make_diagnostic(result, tlv::severity::error);
            diagnostic->diagnostic.location = status.error().location();
            tlv::translate_location(diagnostic->diagnostic.location, base);
        }
    } else
#endif
    {
        std::vector<tlv::tree_frame> frames(std::min(o.max_depth, slice_size));
        tlv::tree_reader reader({reinterpret_cast<const tlv::byte*>(slice), slice_size},
                                *env.format, {frames.data(), frames.size()}, o.max_depth,
                                max_elements);
        // Native adapters are confined to the existing protocol/rendering boundary.
        auto status = visitor
                          ? reader.visit(
                                [&](const tlv::element_view& element, size_t depth, size_t offset) {
                                    return visitor(&element, depth, offset, context);
                                },
                                diagnostic)
                          : reader.validate(diagnostic);
        result = status ? tlv::errc::ok : status.error().status();
        if (result != tlv::errc::ok && diagnostic &&
            tlv::status(diagnostic->diagnostic) != tlv::errc::ok) {
            tlv::translate_location(diagnostic->diagnostic.location, base);
            if (diagnostic->detail.has_tag_offset) diagnostic->detail.tag_offset += base;
            if (diagnostic->detail.has_length_offset) diagnostic->detail.length_offset += base;
            if (diagnostic->detail.has_value_offset) diagnostic->detail.value_offset += base;
            if (diagnostic->detail.has_enclosing_end) diagnostic->detail.enclosing_end += base;
        }
    }
    return result;
}

} // namespace cli
