// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include <tlv/config.h>

// The original CLI requires the composed API, while Document and individual
// protocol formats remain optional. Check the selected public configuration
// for both source builds and installed packages.
#if !OPENTLV_READER || !OPENTLV_WRITER || !OPENTLV_QUERY || !OPENTLV_QUERY_FRONTEND ||             \
    !OPENTLV_SCHEMA || !OPENTLV_CODEC
#error "OpenTLV CLI requires Core Reader, Writer, Query frontend, Schema and Codec capabilities"
#endif
