# TLV JSON document

`otlv decode` writes, and `otlv encode --input` reads, a JSON document that
describes a sequence of TLV elements. This page defines that document, its
version, and what a round trip through it does and does not preserve. Commands
and options are described in the [command-line tool](README.md) guide.

```json
{"schema":"opentlv.tlv","version":1,"format":"ber","elements":[
  {"tag":"E1","length_mode":"definite","children":[
    {"tag":"5A","value":"1234"},
    {"tag":"5A","value":""}]},
  {"tag":"30","length_mode":"indefinite","children":[
    {"tag":"04","value":"AA"}]}]}
```

`decode` prints the document on one line, with the members in the order shown
below; `encode` accepts any member order and any whitespace.

## Document

| Member | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema` | string | yes | Always `"opentlv.tlv"`. |
| `version` | integer | yes | Schema version. This page defines version `1`; any other value is rejected. |
| `format` | string | on output | The wire format (`fixed`, `emv`, `ber`, `der`, `bluetooth-ltv` or `nfc-type2`). Optional on input; when present it must equal `--format`. |
| `elements` | array | yes | The top-level elements in wire order. May be empty. |

Recovered output (`decode --recover`) adds `complete` and `skipped`; see
[Recovery scanning](README.md#recovery-scanning). A document with those
members is not valid input for `encode`, because it is incomplete.

## Elements

Every element is an object with a `tag` and exactly one of `value` or
`children`.

| Member | Type | Meaning |
| --- | --- | --- |
| `tag` | string | The tag bytes in wire order as hexadecimal. Required, at least one byte and at most 8 bytes, the longest tag any built-in format accepts. |
| `value` | string | A **primitive** element: its raw value bytes as hexadecimal. The empty string is an empty value. |
| `children` | array | A **constructed** element: its child elements in wire order. An empty array is an empty constructed element. |
| `length_mode` | string | BER only, constructed elements only: `"definite"` or `"indefinite"`. `decode` always writes it for BER constructed elements. When absent on input, the length is definite. |
| `name`, `description`, `decoded`, `decode_error` | string | Informational annotations written by `decode --module emv` or `decode --module bluetooth` (`description` is EMV-only). Ignored by `encode`. |

Rules that follow from this:

- **Hexadecimal** strings contain complete byte pairs (`0-9`, `a-f`, `A-F`)
  and nothing else: no `0x` prefix, spaces or separators. `decode` writes
  uppercase; `encode` accepts either.
- **Primitive and constructed elements have different representations.** For
  BER and DER the tag decides which is legal: a tag whose constructed bit is
  set must use `children`, any other tag must use `value`. Formats without
  constructed elements (`fixed`, `bluetooth-ltv`, `nfc-type2`) accept only
  `value`.
- **Order and duplicates are kept.** `elements` and `children` are arrays, so
  repeated tags stay repeated and in the same order.
- **Lengths are never stored.** They are derived while encoding, from the
  bytes actually written. A `length` member is an error.
- **Indefinite length is explicit.** `"length_mode":"indefinite"` writes the
  `80` length and the end-of-contents octets `0000`; it is valid only for BER.
  DER has no indefinite lengths, so `encode --format der` rejects it. EOC is
  never an element of the document.
- Members other than those listed, duplicate members, values of the wrong JSON
  type and malformed hexadecimal are rejected.

## Round trip

The contract for `decode` followed by `encode` with the same `--format` is:

- the element **structure** is preserved: the same tags, in the same order,
  with the same nesting;
- **raw primitive values** are preserved byte for byte;
- BER **definite or indefinite** length mode of each constructed element is
  preserved.

Byte-identical output is **not** promised. Length fields are re-derived in the
writer's canonical form, so a non-minimal length such as `5A 81 01 12`
re-encodes as `5A 01 12`. Input that `decode` rejects produces no document.

Encoding checks its own output: the bytes are read back with the format's
reader and validated with the same structural check as `otlv validate` under
the same limits, so the result is always accepted by that reader.

## Format constraints

| Format | `value` | `children` | `length_mode` |
| --- | --- | --- | --- |
| `fixed`, `bluetooth-ltv`, `nfc-type2` | yes | rejected | rejected |
| `ber` | primitive tags | constructed tags | `definite` or `indefinite` |
| `der` | primitive tags | constructed tags | rejected (`indefinite`); `definite` accepted |

The writer of the selected format still applies its own rules, so an element
can be valid in the document and rejected when encoding: an invalid tag, or a
value too long for `fixed` or `bluetooth-ltv`.

## Limits

The CLI resource limits apply. `--max-input-size` bounds the JSON text read and
the bytes produced, `--max-depth` bounds `children` nesting (top-level elements
are at depth zero) and `--max-elements` bounds the total number of elements.
Exceeding one is exit code 3. The document is checked while it is parsed, so
an oversized or too deeply nested document is rejected without being built.

## Errors

A document that is not valid JSON, does not follow this schema, or asks for
something the format cannot represent exits with code 2 and a message such as
`otlv: invalid JSON document: duplicate member "value"` or
`otlv: cannot encode element 1: tag 04 is primitive; use "value" instead of
"children"`. Elements are numbered in document order, depth first, from zero.
An element the writer rejects exits with code 1.

## Versioning

`version` changes whenever the document changes in a way an older reader would
not accept. Because readers reject members they do not know, that includes
adding a member. `otlv` reads and writes exactly the version stated on this
page and rejects every other with `unsupported JSON schema version`.
