// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include <string.h>
#include <tlv/version.h>

int main(void) {
    if (strcmp(tlv_version_string(), OPENTLV_VERSION_STRING) != 0) return 1;
    return strcmp(tlv_version_git_commit_hash(), OPENTLV_GIT_COMMIT_HASH) != 0;
}
