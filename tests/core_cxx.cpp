// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include <cstring>
#include <tlv++/tlv.hpp>

int main() {
    return std::strcmp(tlv::version(), OPENTLV_VERSION_STRING) != 0;
}
