// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "bluetooth.hpp"
#include <cstring>
#include <iomanip>
#include <sstream>
#include "commands/support.hpp"
#include "tlv/config.h"
#if OPENTLV_BLUETOOTH
#include "tlv++/builtins/bluetooth/codec.hpp"
#include "tlv++/builtins/bluetooth/metadata.hpp"
#endif
namespace cli {
bool bluetooth_module(const options& o) {
    return o.module && !std::strcmp(o.module, "bluetooth");
}
const char* bluetooth_name(const tlv::element_view* element) {
#if OPENTLV_BLUETOOTH
    const auto* name = tlv::bluetooth::ad_name(element->tag());
    if (name) return name;
#else
    (void)element;
#endif
    return "Unknown AD Type";
}
#if OPENTLV_BLUETOOTH
namespace {
std::string hex_value(tlv::value_view value) {
    return hex_string(value.as_bytes());
}
std::string uuid_text(uint32_t value, unsigned width) {
    std::ostringstream out;
    out << "0x" << std::uppercase << std::hex << std::setfill('0') << std::setw(width) << value;
    return out.str();
}
std::string uuid_text(const tlv::bluetooth::uuid128& uuid, unsigned) {
    const auto h = hex_string(uuid.bytes, sizeof(uuid.bytes));
    return h.substr(0, 8) + "-" + h.substr(8, 4) + "-" + h.substr(12, 4) + "-" + h.substr(16, 4) +
           "-" + h.substr(20);
}
template <class Codec, class Render>
decode_result decode(const tlv::element_view* element, Render render) {
    const auto    value = Codec::decode(element->value().as_bytes());
    decode_result result;
    result.status = value ? decode_status::ok : decode_status::error;
    result.text = value ? render(*value) : tlv::message(value.error().status());
    return result;
}
template <class Codec> decode_result decode_uuids(const tlv::element_view* element) {
    return decode<Codec>(element, [](const tlv::bluetooth::uuid_list& list) {
        std::string out = "[";
        const auto  count = list.raw.size() / list.uuid_size;
        for (size_t i = 0; i < count; ++i) {
            if (i) out += ", ";
            if (list.uuid_size == 2)
                out += uuid_text(*tlv::bluetooth::uuid_at<uint16_t>(list, i), 4);
            else if (list.uuid_size == 4)
                out += uuid_text(*tlv::bluetooth::uuid_at<uint32_t>(list, i), 8);
            else
                out += uuid_text(*tlv::bluetooth::uuid_at<tlv::bluetooth::uuid128>(list, i), 0);
        }
        return out + "]";
    });
}
template <class T> std::string service(const T& value, unsigned width) {
    return "UUID=" + uuid_text(value.uuid, width) + " payload=" + hex_value(value.payload);
}
} // namespace
#endif
decode_result decode_bluetooth_value(const tlv::element_view* element) {
#if OPENTLV_BLUETOOTH
    if (element->tag().size() != 1) return {};
    const unsigned type = static_cast<unsigned>(element->tag().as_bytes()[0]);
    switch (type) {
        case 0x01:
            return decode<tlv::bluetooth::flags_codec>(element, [](tlv::value_view value) {
                return !value.empty() ? "0x" + hex_value(value) : "0x00";
            });
        case 0x08:
        case 0x09:
            return decode<tlv::bluetooth::local_name_codec>(element, [](tlv::value_view value) {
                const auto bytes = value;
                return bytes.empty()
                           ? std::string()
                           : std::string(reinterpret_cast<const char*>(bytes.data()), bytes.size());
            });
        case 0x0A:
            return decode<tlv::bluetooth::tx_power_codec>(element, [](int8_t value) {
                return std::to_string(static_cast<int>(value)) + " dBm";
            });
        case 0x02:
        case 0x03:
        case 0x04:
        case 0x05:
        case 0x06:
        case 0x07: {
            if (type <= 3) return decode_uuids<tlv::bluetooth::uuid16_list_codec>(element);
            if (type <= 5) return decode_uuids<tlv::bluetooth::uuid32_list_codec>(element);
            return decode_uuids<tlv::bluetooth::uuid128_list_codec>(element);
        }
        case 0x16:
            return decode<tlv::bluetooth::service_data16_codec>(
                element,
                [](const tlv::bluetooth::service_data16& value) { return service(value, 4); });
        case 0x20:
            return decode<tlv::bluetooth::service_data32_codec>(
                element,
                [](const tlv::bluetooth::service_data32& value) { return service(value, 8); });
        case 0x21:
            return decode<tlv::bluetooth::service_data128_codec>(
                element,
                [](const tlv::bluetooth::service_data128& value) { return service(value, 0); });
        case 0xFF:
            return decode<tlv::bluetooth::manufacturer_data_codec>(
                element, [](const tlv::bluetooth::manufacturer_data& value) {
                    const auto* name = tlv::bluetooth::company_name(value.company_id);
                    return "company=" + uuid_text(value.company_id, 4) + " (" +
                           (name ? name : "Unknown Company Identifier") +
                           ") payload=" + hex_value(value.payload);
                });
        default: break;
    }
#else
    (void)element;
#endif
    return {};
}
} // namespace cli
