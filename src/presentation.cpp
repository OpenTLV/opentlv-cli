// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "presentation.hpp"
#include "tlv/config.h"
#include <cassert>
#include <iostream>
#include <sstream>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <unistd.h>
#endif
#if OPENTLV_EMV
#include "tlv++/builtins/emv/dictionary.hpp"
#endif

static int environment_excludes_color(void) {
#ifdef _WIN32
    char  value[32];
    DWORD length;
    SetLastError(ERROR_SUCCESS);
    length = GetEnvironmentVariableA("NO_COLOR", value, sizeof(value));
    if (length || GetLastError() != ERROR_ENVVAR_NOT_FOUND) return 1;
    length = GetEnvironmentVariableA("TERM", value, sizeof(value));
    return length && length < sizeof(value) && !strcmp(value, "dumb");
#else
    const char* term = getenv("TERM");
    return getenv("NO_COLOR") != NULL || (term && !strcmp(term, "dumb"));
#endif
}

void cli_presentation_init(cli_presentation_t* p, const uint8_t* data, size_t size, int color,
                           int pretty) {
    int terminal;
    *p = cli_presentation_t{};
    p->ends.resize(1);
    p->more.resize(1);
    p->contexts.resize(1);
    p->data = data;
    p->ends[0] = size;
#ifdef _WIN32
    terminal = GetConsoleMode(GetStdHandle(STD_OUTPUT_HANDLE), &p->console_mode) != 0;
#else
    terminal = isatty(STDOUT_FILENO);
    (void)pretty;
#endif
    p->color = color > 0 || (color == 0 && terminal && !environment_excludes_color());
#ifdef _WIN32
    if (terminal && p->color) {
        p->restore_mode = SetConsoleMode(GetStdHandle(STD_OUTPUT_HANDLE),
                                         p->console_mode | ENABLE_VIRTUAL_TERMINAL_PROCESSING) != 0;
        if (!p->restore_mode && color == 0) p->color = 0;
    }
    if (terminal && pretty) {
        p->console_codepage = GetConsoleOutputCP();
        p->restore_codepage = SetConsoleOutputCP(CP_UTF8) != 0;
    }
#endif
}

void cli_presentation_restore(cli_presentation_t* p) {
#ifdef _WIN32
    /* Flush UTF-8 bytes before restoring the console's original encoding. */
    std::cout.flush();
    if (p->restore_mode) SetConsoleMode(GetStdHandle(STD_OUTPUT_HANDLE), p->console_mode);
    if (p->restore_codepage) SetConsoleOutputCP(p->console_codepage);
#else
    (void)p;
#endif
}

size_t cli_element_value_size(const tlv::element_view* element) {
    return element->value().size();
}

void cli_presentation_visit(cli_presentation_t* p, const tlv::element_view* element, size_t depth,
                            int indefinite) {
    size_t end =
        static_cast<size_t>(reinterpret_cast<const uint8_t*>(element->value().data()) - p->data) +
        cli_element_value_size(element);
    p->ends.resize(depth + 2);
    p->more.resize(depth + 2);
    p->contexts.resize(depth + 2);
    p->more[depth] = end + (indefinite ? 2u : 0u) < p->ends[depth];
    {
        p->ends[depth + 1] = end;
#if OPENTLV_EMV
        p->contexts[depth + 1] = static_cast<int>(tlv::emv::child_context(
            static_cast<tlv::emv::context>(p->contexts[depth]), element->tag()));
#endif
    }
}

void cli_presentation_prefix(const cli_presentation_t* p, size_t depth) {
    size_t i;
    for (i = 1; i < depth; ++i) std::cout << (p->more[i] ? "\xE2\x94\x82   " : "    ");
    if (depth)
        std::cout << (p->more[depth] ? "\xE2\x94\x9C\xE2\x94\x80\xE2\x94\x80 "
                                     : "\xE2\x94\x94\xE2\x94\x80\xE2\x94\x80 ");
}

cli_emv_info cli_presentation_emv_info(const cli_presentation_t* p,
                                       const tlv::element_view* element, size_t depth,
                                       int describe) {
    cli_emv_info info;
#if OPENTLV_EMV
    const auto definition = tlv::emv::dictionary(static_cast<tlv::emv::context>(p->contexts[depth]))
                                .find(element->tag());
    if (!definition) return info;
    info.known = true;
    info.name = definition.name();
    if (describe) {
        std::ostringstream description;
        description << tlv::emv::description(definition.kind())
                    << "; dictionary length: " << definition.length().minimum;
        if (definition.length().maximum == SIZE_MAX)
            description << "..unbounded";
        else if (definition.length().maximum != definition.length().minimum)
            description << ".." << definition.length().maximum;
        description << " bytes; step: " << definition.length_step();
        info.has_description = true;
        info.description = description.str();
    }
#else
    (void)p;
    (void)element;
    (void)depth;
    (void)describe;
#endif
    return info;
}

void cli_presentation_emv(const cli_presentation_t* p, const tlv::element_view* element,
                          size_t depth, int describe) {
    const cli_emv_info info = cli_presentation_emv_info(p, element, depth, describe);
    std::cout << " name=\"" << (info.known ? info.name : "Unknown EMV tag in this context") << '"';
    if (info.has_description) std::cout << " description=\"" << info.description << '"';
}
