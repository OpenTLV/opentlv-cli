// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_DIAGNOSTIC_COLLECT_HPP
#define OPENTLV_CLI_DIAGNOSTIC_COLLECT_HPP
#include <cstddef>
#include <vector>
#include <cstdint>
#include "tlv++/diagnostic.hpp"
#include "tlv++/format.hpp"
#include "tlv++/types.hpp"
#include "tlv++/visitor.hpp"

// Collects the detail behind a traversal's diagnostic (the path enclosing it, and
// enough of a reader diagnostic to describe it) independently of how that
// detail is later presented. diagnostic_render.hpp owns formatting only;
// this file owns figuring out what there is to format.

namespace cli {

// The tags and value boundaries enclosing whichever element a traversal's visitor
// was last called for. Independent of cli_presentation_t, which exists only
// for display bookkeeping (indentation, EMV context inheritance) and must
// not be reused here. One instance is shared by every visitor of a single
// traversal.
struct diagnostic_scope {
    tlv::diagnostic_path path;
    // end[d]: offset one past the value of the scope open at depth d;
    // end[0] is the whole input size.
    std::vector<size_t> end;
};

// Resets `scope` to an empty path within an input of `size` bytes.
void diagnostic_scope_init(diagnostic_scope& scope, size_t size);

// Updates `scope` for the element just visited at `depth`, before doing
// anything else with it, so that a later failure deeper in the same traversal can
// be reported with the tags and value boundary enclosing it. Mirrors the
// pop-then-push pattern in docs/guides/diagnostics.md#hierarchical-paths.
// `base` is the start of the whole input buffer, used to compute a
// constructed value's absolute end from its borrowed pointer; `constructed`
// is the same nesting predicate passed to the traversal, or `nullptr`.
void diagnostic_scope_visit(diagnostic_scope& scope, const uint8_t* base,
                            const tlv::element_view* element, std::size_t depth,
                            const tlv::format& format);

} // namespace cli
#endif
