// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "diagnostic_collect.hpp"
#include <cassert>

namespace cli {

void diagnostic_scope_init(diagnostic_scope& scope, size_t size) {
    scope.path = tlv::make_diagnostic_path();
    scope.end.assign(1, size);
}

void diagnostic_scope_visit(diagnostic_scope& scope, const uint8_t* base,
                            const tlv::element_view* element, size_t depth,
                            const tlv::format& format) {
    // Every entered scope contributes a logical frame, including omitted tags.
    while (scope.path.length > depth || scope.path.omitted > depth - scope.path.length)
        tlv::pop_path(scope.path);
    if (!format.is_constructed(element->tag())) return;
    if (element->value().data()) {
        scope.end.resize(depth + 2);
        scope.end[depth + 1] =
            static_cast<size_t>(reinterpret_cast<const uint8_t*>(element->value().data()) - base) +
            element->value().size();
    }
    const auto pushed = tlv::push_path(scope.path, element->tag());
    if (!pushed) {
        // A full path has already counted this frame in omitted. Continue the
        // traversal with that explicit truncation and unwind it on later visits.
        assert(pushed.error().status() == tlv::errc::buffer_too_short);
    }
}

} // namespace cli
