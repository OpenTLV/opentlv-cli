// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel
#include "commands/generate_command.hpp"
#include "commands/support.hpp"
#include "commands/decode_command.hpp"
#include "diagnostics.hpp"
#include "tlv++/generator.hpp"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <sys/stat.h>
#include <fcntl.h>
#ifdef _WIN32
#include <direct.h>
#include <io.h>
#else
#include <unistd.h>
#endif

namespace {
bool exists(const std::string& path) {
    struct stat info;
    return stat(path.c_str(), &info) == 0;
}
bool directory(const std::string& path) {
    struct stat info;
    return stat(path.c_str(), &info) == 0 && (info.st_mode & S_IFMT) == S_IFDIR;
}
bool make_directory(const std::string& path) {
    if (directory(path)) return true;
    const auto separator = path.find_last_of("/\\");
    if (separator != std::string::npos && separator > 0 &&
        !make_directory(path.substr(0, separator)))
        return false;
#ifdef _WIN32
    return _mkdir(path.c_str()) == 0 || directory(path);
#else
    return mkdir(path.c_str(), 0777) == 0 || directory(path);
#endif
}
std::string case_path(const std::string& directory, uint64_t index,
                      const char* extension = ".bin") {
    std::ostringstream name;
    name << directory << '/' << std::setw(6) << std::setfill('0') << index << extension;
    return name.str();
}
bool write_case(const std::string& path, const void* data, size_t size) {
#ifdef _WIN32
    const int descriptor =
        _open(path.c_str(), _O_WRONLY | _O_CREAT | _O_EXCL | _O_BINARY, _S_IREAD | _S_IWRITE);
    FILE* file = descriptor < 0 ? nullptr : _fdopen(descriptor, "wb");
#else
    const int descriptor = open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0666);
    FILE*     file = descriptor < 0 ? nullptr : fdopen(descriptor, "wb");
#endif
    if (!file) {
        if (descriptor >= 0) {
#ifdef _WIN32
            _close(descriptor);
#else
            close(descriptor);
#endif
            std::remove(path.c_str());
        }
        return false;
    }
    const bool written = fwrite(data, 1, size, file) == size;
    const bool closed = fclose(file) == 0;
    if (!written || !closed) std::remove(path.c_str());
    return written && closed;
}
} // namespace

namespace cli {
int generate_command::run() try {
    const auto&      o = options_;
    format_selection selection(o);
    auto             format = selection.get();
    if (!format) return fail(2, "unknown, disabled format or invalid format configuration");

    // Stable ordered wire domains, independent of semantic dictionaries/codecs.
    std::vector<std::vector<tlv::byte>> tags;
    size_t                              value_limit = o.max_value_size;
    bool                                nested = false;
    if (!strcmp(o.format, "fixed")) {
        tags.emplace_back(o.fixed_tag_size, static_cast<tlv::byte>(1));
        if (o.fixed_length_size < sizeof(size_t))
            value_limit = std::min(value_limit, (size_t(1) << (o.fixed_length_size * 8)) - 1);
    } else if (!strcmp(o.format, "ber") || !strcmp(o.format, "der") || !strcmp(o.format, "emv")) {
        tags = {{static_cast<tlv::byte>(0x04)},
                {static_cast<tlv::byte>(0x80)},
                {static_cast<tlv::byte>(0x30)},
                {static_cast<tlv::byte>(0xA0)}};
        nested = true;
    } else if (!strcmp(o.format, "bluetooth-ltv")) {
        tags = {{static_cast<tlv::byte>(0x09)}, {static_cast<tlv::byte>(0xFF)}};
        value_limit = std::min(value_limit, size_t(254));
    } else if (!strcmp(o.format, "nfc-type2")) {
        tags = {{static_cast<tlv::byte>(0x03)}, {static_cast<tlv::byte>(0xFD)}};
        value_limit = std::min(value_limit, size_t(65534));
    } else
        return fail(2, "format has no supported generation domain");
    std::vector<tlv::generator_candidate> candidates;
    for (const auto& tag : tags)
        candidates.push_back(
            tlv::make_generator_candidate(tlv::tag({tag.data(), tag.size()}), 0, value_limit));
    tlv::generator_options options{};
    options.seed = o.seed;
    options.max_elements = o.max_elements;
    options.max_depth = nested ? o.max_depth : 0;
    options.max_value_size = value_limit;
    options.max_case_size = o.max_case_size;
    options.candidates = candidates.data();
    options.candidate_count = candidates.size();
    tlv::generator generator(*format, options);
    // Reject impossible configurations before creating any output.
    auto first = generator.generate(0);
    if (!first)
        return fail(3, (std::string("cannot generate case 0 for selected format/limits: ") +
                        first.error().message())
                           .c_str());
    std::string output_dir(o.output_dir);
    while (output_dir.size() > 1 && (output_dir.back() == '/' || output_dir.back() == '\\'))
        output_dir.pop_back();
    const char* extension = o.json_output ? ".json" : ".bin";
    for (uint64_t i = 0; i < o.count; ++i) {
        const auto path = case_path(output_dir, i, extension);
        if (exists(path))
            return fail(3, (std::string("refusing to overwrite case: ") + path).c_str());
    }
    if (!make_directory(output_dir)) return fail(3, "cannot create output directory");
    for (uint64_t i = 0; i < o.count; ++i) {
        auto wire = i == 0 ? std::move(first) : generator.generate(i);
        if (!wire)
            return fail(3, (std::string("cannot generate case ") + std::to_string(i) + ": " +
                            wire.error().message())
                               .c_str());
        std::string json;
        if (o.json_output) {
            cli::options decode_options = o;
            decode_options.command = "decode";
            decode_options.max_input = o.max_case_size;
            decode_options.max_depth = options.max_depth;
            std::vector<uint8_t> input(wire->size());
            std::memcpy(input.data(), wire->data(), wire->size());
            std::ostringstream output;
            decode_command     decoder(decode_options, std::move(input), output);
            if (decoder.run() != 0)
                return fail(
                    3, (std::string("cannot decode JSON for case ") + std::to_string(i)).c_str());
            json = output.str();
        }
        const auto   path = case_path(output_dir, i, extension);
        const void*  data = o.json_output ? static_cast<const void*>(json.data()) : wire->data();
        const size_t size = o.json_output ? json.size() : wire->size();
        if (!write_case(path, data, size))
            return fail(3, (std::string("cannot create/write case: ") + path).c_str());
    }
    return 0;
} catch (const std::length_error&) {
    return fail(3, "generation limits exceed available C++ storage capacity");
}
} // namespace cli
