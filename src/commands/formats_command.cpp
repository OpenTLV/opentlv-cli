// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "commands/formats_command.hpp"
#include <iostream>
#include "diagnostics.hpp"
#include "tlv/config.h"

namespace cli {

std::vector<std::string> enabled_formats() {
    std::vector<std::string> names;
    names.push_back("fixed");
#if OPENTLV_EMV
    names.push_back("emv");
#endif
#if OPENTLV_FORMAT_BER
    names.push_back("ber");
#endif
#if OPENTLV_FORMAT_DER
    names.push_back("der");
#endif
#if OPENTLV_BLUETOOTH
    names.push_back("bluetooth-ltv");
#endif
#if OPENTLV_NFC
    names.push_back("nfc-type2");
#endif
    return names;
}

int formats_command::run() {
    for (const std::string& name : enabled_formats()) std::cout << name << "\n";
    return flush_stdout();
}

} // namespace cli
