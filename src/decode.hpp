// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_DECODE_HPP
#define OPENTLV_CLI_DECODE_HPP
#include <string>
#include "tlv++/types.hpp"
#include "tlv++/visitor.hpp"

namespace cli {

// Outcome of attempting to decode a TLV value through the OpenTLV EMV codec
// layer. `unavailable` is not an error: it covers a tag with no dictionary
// entry in the given context and a known tag whose value kind carries no
// codec (BYTES, TEXT, TEMPLATE), both of which leave the raw value as the
// only representation.
enum class decode_status { unavailable, ok, error };

struct decode_result {
    decode_status status = decode_status::unavailable;
    std::string   text; // decoded, human-readable value (ok) or diagnostic (error)
};

// Looks `element`'s tag up in the EMV dictionary under `context` (a
// tlv_emv_context_t, passed as int so this header does not require the EMV
// module to be compiled in) and, if it carries a codec, decodes its value
// through tlv_codec_decode and formats the result for display. `element`'s raw
// value is never modified; callers present it independently. Builds on the
// codec layer only - no decoding logic is implemented here beyond formatting
// the codec's own output.
decode_result decode_emv_value(int context, const tlv::element_view* element);

} // namespace cli
#endif
