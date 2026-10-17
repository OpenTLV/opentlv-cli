// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "decode.hpp"
#include "presentation.hpp"
#include "tlv/config.h"
#if OPENTLV_EMV
#include <cinttypes>
#include <cstdio>
#include <limits>
#include "tlv++/builtins/emv/codec.hpp"
#include "tlv++/builtins/emv/dictionary.hpp"
#endif

namespace cli {

#if OPENTLV_EMV
namespace {

std::string format_number(const uint64_t& value) {
    return std::to_string(value);
}

std::string format_flags(const uint64_t& value) {
    char buffer[2 + 16 + 1];
    std::snprintf(buffer, sizeof(buffer), "0x%" PRIX64, value);
    return buffer;
}

std::string format_date(const tlv::emv::date& date) {
    char buffer[16];
    std::snprintf(buffer, sizeof(buffer), "20%02u-%02u-%02u", (unsigned)date.year,
                  (unsigned)date.month, (unsigned)date.day);
    return buffer;
}

std::string format_time(const tlv::emv::time& time) {
    char buffer[16];
    std::snprintf(buffer, sizeof(buffer), "%02u:%02u:%02u", (unsigned)time.hour,
                  (unsigned)time.minute, (unsigned)time.second);
    return buffer;
}

const char* account_name(tlv::emv::account account) {
    switch (account) {
        case tlv::emv::savings_account: return "savings";
        case tlv::emv::debit_account: return "cheque/debit";
        case tlv::emv::credit_account: return "credit";
        default: return "default";
    }
}

const char* cryptogram_name(decltype(tlv::emv::cryptogram{}.type) type) {
    switch (type) {
        case tlv::emv::aac: return "AAC";
        case tlv::emv::tc: return "TC";
        case tlv::emv::arqc: return "ARQC";
        default: return "RFU";
    }
}

std::string format_cryptogram(const tlv::emv::cryptogram& info) {
    char buffer[32];
    std::snprintf(buffer, sizeof(buffer), "%s (flags=0x%02X)", cryptogram_name(info.type),
                  (unsigned)info.flags);
    return buffer;
}

const char* biometric_name(tlv::emv::biometric type) {
    switch (type) {
        case tlv::emv::facial: return "facial";
        case tlv::emv::voice: return "voice";
        case tlv::emv::finger: return "finger";
        case tlv::emv::iris: return "iris";
        case tlv::emv::palm: return "palm";
        default: return "unknown";
    }
}

std::string format_number_list(const tlv::emv::number_list& list) {
    std::string result;
    for (size_t i = 0; i < list.count; ++i) {
        if (i) result += ',';
        result += std::to_string(list.values[i]);
    }
    return result;
}

std::string format_afl(const tlv::emv::afl& afl) {
    std::string result;
    char        entry[64];
    for (size_t i = 0; i < afl.count; ++i) {
        if (i) result += ';';
        std::snprintf(entry, sizeof(entry), "sfi=%u records=%u-%u offline=%u",
                      (unsigned)afl.entries[i].sfi, (unsigned)afl.entries[i].first_record,
                      (unsigned)afl.entries[i].last_record,
                      (unsigned)afl.entries[i].offline_auth_record_count);
        result += entry;
    }
    return result;
}

const char* cvm_result_name(uint8_t result) {
    switch (result) {
        case tlv::emv::verification_failed: return "failed";
        case tlv::emv::verification_succeeded: return "successful";
        default: return "unknown";
    }
}

std::string format_cvm_result(const tlv::emv::cvm_result& result) {
    char buffer[64];
    std::snprintf(buffer, sizeof(buffer), "method=0x%02X condition=0x%02X result=%s",
                  (unsigned)result.method, (unsigned)result.condition,
                  cvm_result_name(result.result));
    return buffer;
}

std::string format_track2(const tlv::emv::track2& track2) {
    char buffer[128];
    std::snprintf(buffer, sizeof(buffer), "pan=%s exp=%02u/%02u service=%03u discretionary=%s",
                  track2.pan, (unsigned)track2.expiration_year, (unsigned)track2.expiration_month,
                  (unsigned)track2.service_code, track2.discretionary_data);
    return buffer;
}

template <typename T>
decode_result decode_fixed(tlv::dynamic_codec codec, tlv::bytes input,
                           std::string (*format)(const T&)) {
    decode_result result;
    auto          value = codec.decode<T>(input);
    if (!value) {
        result.status = decode_status::error;
        result.text = value.error().message();
        return result;
    }
    result.status = decode_status::ok;
    result.text = format(*value);
    return result;
}

decode_result decode_digits(tlv::dynamic_codec codec, tlv::bytes input) {
    decode_result result;
    const size_t  size = input.size();
    // The codec writes at most 2 digits per input byte, plus a NUL terminator.
    if (size > (std::numeric_limits<size_t>::max)() / 2 - 1) {
        result.status = decode_status::error;
        result.text = "value too large to decode";
        return result;
    }
    std::string buffer(size * 2 + 1, '\0');
    auto        decoded = codec.decode_into(input, tlv::span<char>(&buffer[0], buffer.size()));
    if (!decoded) {
        result.status = decode_status::error;
        result.text = decoded.error().message();
        return result;
    }
    result.status = decode_status::ok;
    result.text = buffer.c_str();
    return result;
}

} // namespace
#endif

decode_result decode_emv_value(int context, const tlv::element_view* element) {
    decode_result result;
#if OPENTLV_EMV
    const tlv::emv::dictionary dictionary(static_cast<tlv::emv::context>(context));
    const auto                 definition = dictionary.find(element->tag());
    if (!definition || !definition.codec().readable()) return result;
    const tlv::bytes input = element->value().as_bytes();
    switch (definition.kind()) {
        case tlv::emv::value_kind::number:
            return decode_fixed<uint64_t>(definition.codec(), input, format_number);
        case tlv::emv::value_kind::flags:
            return decode_fixed<uint64_t>(definition.codec(), input, format_flags);
        case tlv::emv::value_kind::digits: return decode_digits(definition.codec(), input);
        case tlv::emv::value_kind::date:
            return decode_fixed<tlv::emv::date>(definition.codec(), input, format_date);
        case tlv::emv::value_kind::time:
            return decode_fixed<tlv::emv::time>(definition.codec(), input, format_time);
        case tlv::emv::value_kind::account:
            return decode_fixed<tlv::emv::account>(
                definition.codec(), input, [](const tlv::emv::account& account) -> std::string {
                    return account_name(account);
                });
        case tlv::emv::value_kind::cryptogram:
            return decode_fixed<tlv::emv::cryptogram>(definition.codec(), input, format_cryptogram);
        case tlv::emv::value_kind::biometric:
            return decode_fixed<tlv::emv::biometric>(
                definition.codec(), input, [](const tlv::emv::biometric& biometric) -> std::string {
                    return biometric_name(biometric);
                });
        case tlv::emv::value_kind::number_list:
            return decode_fixed<tlv::emv::number_list>(definition.codec(), input,
                                                       format_number_list);
        case tlv::emv::value_kind::afl:
            return decode_fixed<tlv::emv::afl>(definition.codec(), input, format_afl);
        case tlv::emv::value_kind::cvm_result:
            return decode_fixed<tlv::emv::cvm_result>(definition.codec(), input, format_cvm_result);
        case tlv::emv::value_kind::track2:
            return decode_fixed<tlv::emv::track2>(definition.codec(), input, format_track2);
        default: return result; // BYTES, TEXT, TEMPLATE: no codec, already returned above
    }
#else
    (void)context;
    (void)element;
    return result;
#endif
}

} // namespace cli
