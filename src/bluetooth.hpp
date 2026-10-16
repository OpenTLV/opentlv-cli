// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_BLUETOOTH_HPP
#define OPENTLV_CLI_BLUETOOTH_HPP
#include "decode.hpp"
#include "options.hpp"
namespace cli {
// Presentation only: registry names and formatted results of public value codecs.
// Unknown types have no decoded annotation; no wire or payload parser lives here.
bool          bluetooth_module(const options& options);
const char*   bluetooth_name(const tlv::element_view* element);
decode_result decode_bluetooth_value(const tlv::element_view* element);
template <class Json>
void json_bluetooth(Json& object, const tlv::element_view* element, bool decode) {
    object["name"] = bluetooth_name(element);
    if (!decode) return;
    const auto result = decode_bluetooth_value(element);
    if (result.status == decode_status::ok) object["decoded"] = result.text;
    if (result.status == decode_status::error) object["decode_error"] = result.text;
}
} // namespace cli
#endif
