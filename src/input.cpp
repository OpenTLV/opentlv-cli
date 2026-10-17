// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "input.hpp"
#include "diagnostics.hpp"
#include <cctype>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

namespace {

int nibble(unsigned char ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    return -1;
}

int append(std::vector<uint8_t>& data, std::size_t limit, uint8_t byte) {
    if (data.size() == limit) return cli::fail(3, "input-size limit exceeded");
    data.push_back(byte);
    return 0;
}

} // namespace

namespace cli {

int decode_hex(const char* text, std::size_t limit, std::vector<uint8_t>& data) {
    const unsigned char* p = (const unsigned char*)text;
    while (*p) {
        int hi, lo, rc;
        if (isspace(*p)) {
            ++p;
            continue;
        }
        hi = nibble(*p++);
        if (hi < 0 || !*p || (lo = nibble(*p++)) < 0)
            return fail(2, "hex input requires complete hexadecimal byte pairs");
        rc = append(data, limit, (uint8_t)(hi * 16 + lo));
        if (rc) return rc;
    }
    return 0;
}

int read_input(const options& o, std::vector<uint8_t>& data) {
    int rc = 0;
    if (o.hex) {
        return decode_hex(o.hex, o.max_input, data);
    } else {
        std::ifstream file;
        std::istream* stream = &std::cin;
        int           ch, high = -1;
        if (strcmp(o.input, "-")) {
            file.open(o.input, std::ios::binary);
            if (!file) return fail(3, "cannot open input file");
            stream = &file;
        }
#ifdef _WIN32
        else if (_setmode(_fileno(stdin), _O_BINARY) == -1)
            return fail(3, "cannot set binary stdin mode");
#endif
        while ((ch = stream->get()) != std::char_traits<char>::eof()) {
            if (o.hex_input) {
                int digit;
                if (high < 0 && isspace((unsigned char)ch)) continue;
                digit = nibble((unsigned char)ch);
                if (digit < 0) {
                    rc = fail(2, "hex input requires complete hexadecimal byte pairs");
                    break;
                }
                if (high < 0) {
                    high = digit;
                    continue;
                }
                ch = high * 16 + digit;
                high = -1;
            }
            rc = append(data, o.max_input, (uint8_t)ch);
            if (rc) break;
        }
        if (!rc && stream->bad()) rc = fail(3, "cannot read input");
        if (!rc && high >= 0) rc = fail(2, "hex input requires complete hexadecimal byte pairs");
        if (stream == &file) {
            // Reaching EOF/a decode error already left failbit set; clear it so
            // the post-close check reflects only close()'s own outcome.
            file.clear();
            file.close();
            if (!rc && !file) rc = fail(3, "cannot close input");
        }
    }
    return rc;
}

int read_text(const char* path, std::size_t limit, std::string& text) {
    std::ifstream file;
    std::istream* stream = &std::cin;
    int           ch;
    if (strcmp(path, "-")) {
        file.open(path, std::ios::binary);
        if (!file) return fail(3, "cannot open input file");
        stream = &file;
    }
#ifdef _WIN32
    else if (_setmode(_fileno(stdin), _O_BINARY) == -1)
        return fail(3, "cannot set binary stdin mode");
#endif
    while ((ch = stream->get()) != std::char_traits<char>::eof()) {
        if (text.size() == limit) return fail(3, "input-size limit exceeded");
        text.push_back((char)ch);
    }
    if (stream->bad()) return fail(3, "cannot read input");
    return 0;
}

} // namespace cli
