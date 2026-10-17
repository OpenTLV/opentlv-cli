// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include <stdio.h>
#include <tlv/config.h>

int main(void) {
    puts("set(HAS_FIXED 1)");
    printf("set(HAS_BER %d)\n", OPENTLV_FORMAT_BER);
    printf("set(HAS_DER %d)\n", OPENTLV_FORMAT_DER);
    printf("set(HAS_EMV %d)\n", OPENTLV_EMV);
    printf("set(HAS_BLUETOOTH_LTV %d)\n", OPENTLV_BLUETOOTH);
    printf("set(HAS_NFC %d)\n", OPENTLV_NFC);
    printf("set(HAS_DOCUMENT %d)\n", OPENTLV_DOCUMENT);
    printf("set(HAS_QUERY_FRONTEND %d)\n", OPENTLV_QUERY_FRONTEND);
    return 0;
}
