// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel
#include "commands/diff_command.hpp"
#include "commands/support.hpp"
#include "diagnostics.hpp"
#include "input.hpp"
#include <nlohmann/json.hpp>
#if OPENTLV_DOCUMENT
#include "tlv++/document/diff.hpp"
#endif
namespace cli {
int diff_command::run() {
#if OPENTLV_DOCUMENT
    format_selection formats(options_);
    auto             format = formats.get();
    if (!format) return fail(2, "unknown or disabled format");
    options rhs_options = options_;
    rhs_options.input = options_.against;
    std::vector<uint8_t> rhs_input;
    auto                 status = read_input(rhs_options, rhs_input);
    if (status) return status;
    tlv::document_format settings(*format);
    settings.max_depth = options_.max_depth;
    settings.max_elements = options_.max_elements;
    auto view = [](const std::vector<uint8_t>& data) {
        return tlv::bytes(reinterpret_cast<const tlv::byte*>(data.data()), data.size());
    };
    auto left = tlv::document::parse(view(input_), settings);
    auto right = tlv::document::parse(view(rhs_input), settings);
    if (!left || !right) return fail(3, "invalid diff input");
    std::unique_ptr<tlv::query_program> where;
    if (options_.where) {
        auto compiled = tlv::query_program::compile(options_.where);
        if (!compiled) return fail(2, tlv::message(compiled.error().status()));
        where.reset(new tlv::query_program(std::move(*compiled)));
    }
    auto changes = tlv::semantic_diff(*left, *right, where.get());
    if (!changes) return fail(3, tlv::message(changes.error().status()));
    nlohmann::json results = nlohmann::json::array();
    for (const auto& change : *changes) {
        const char* kind = change.kind == tlv::diff_kind::added     ? "added"
                           : change.kind == tlv::diff_kind::removed ? "removed"
                                                                    : "changed";
        auto        value = [](const tlv::const_node& n) -> nlohmann::json {
            if (!n) return nullptr;
            return nlohmann::json{
                {"constructed", n.is_constructed()},
                {"value", n.is_constructed() ? nlohmann::json(nullptr)
                                             : nlohmann::json(hex_string(n.value().as_bytes()))}};
        };
        if (is_json(options_))
            results.push_back({{"kind", kind},
                               {"path", change.path},
                               {"left", value(change.left)},
                               {"right", value(change.right)}});
        else
            std::cout << kind << ' ' << change.path << '\n';
    }
    if (is_json(options_)) std::cout << nlohmann::json({{"changes", results}}).dump() << '\n';
    return flush_stdout();
#else
    return fail(2, "diff requires the Document component");
#endif
}
} // namespace cli
