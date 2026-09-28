# YaFT Specification

Normative rules for every YaFT implementation. The reference implementation is
[`@tehw0lf/yaft`](https://github.com/tehw0lf/yaft) (TypeScript); where this
document and the reference disagree, **this document wins** and the reference
is a bug.

Rules are numbered `R1`, `R2`, … and never renumbered. A rule that is retired
keeps its number and is marked withdrawn, so a `rule` reference in an old case
file never silently points at something else.

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119.

## 1. Data model

A **feature** is a record with these fields:

| Field | Type | Notes |
|---|---|---|
| `key` | string | unique within a provider |
| `value` | string | `"true"` or `"false"` — a string, not a boolean |
| `activeAt` | string, nullable | RFC 3339 with offset, or unset |
| `disabledAt` | string, nullable | RFC 3339 with offset, or unset |
| `tags` | string array | optional |

**R1.** `value` MUST be treated as a string. The backend stores it as one, and
a port that coerces it to a boolean at the edges will disagree with the backend
about values like `"1"` or `"yes"`.

**R2.** `activeAt` and `disabledAt` are optional bounds. A port MUST treat
`null`, an empty string and an absent field as the same thing: no bound.

## 2. Evaluation

The core of every port is a single function that answers whether a feature is
on at a given instant.

```
function isEnabled(key, now):
    feature = data[key]
    if feature is null or missing:          return false
    if feature.value != "true":             return false

    t = parseTimestamp(feature.activeAt)
    if t is valid and now < t:              return false

    t = parseTimestamp(feature.disabledAt)
    if t is valid and now >= t:             return false

    return true
```

**R3.** A missing key, a `null` feature or an absent feature MUST evaluate to
`false`.

**R4.** Only the exact string `"true"` MUST evaluate to on. `"TRUE"`, `"True"`,
`"1"`, `"yes"`, `""` and an absent `value` MUST evaluate to `false`.
Comparison is case-sensitive and exact — no trimming, no coercion.

**R5.** `now < activeAt` MUST evaluate to `false`. The window is half-open at
this end: at exactly `activeAt` the feature is **on**.

**R6.** `now >= disabledAt` MUST evaluate to `false`. At exactly `disabledAt`
the feature is **off** — the opposite boundary behaviour from R5. The two
together make the window `[activeAt, disabledAt)`.

**R7.** An `activeAt` later than `disabledAt` MUST NOT be special-cased. It
yields a window that is never open, and a port MUST NOT swap the bounds, warn,
or throw.

**R8.** A bound that is unset or does not parse under R9–R12 MUST be ignored —
treated as no bound, not as an error and not as a bound of zero. Evaluation
MUST NOT throw for any input. A port SHOULD log a warning when it ignores a
malformed bound.

**R9.** The clock MUST be injectable, defaulting to system time. Without this a
port cannot run the conformance suite, which supplies `now` per case, and its
own time-dependent tests cannot be deterministic.

## 3. Timestamps

**R10.** Only RFC 3339 with an explicit offset is valid:

```
YYYY-MM-DDThh:mm:ss[.fff](Z|±hh:mm)
```

`T` and `Z` MAY be lowercase. Fractional seconds MAY be present with any number
of digits. Everything else is invalid under R8 and therefore ignored —
specifically a bare date (`2026-09-18`), a timestamp without an offset
(`2026-09-18T15:00:00`), a Unix timestamp, and any other separator or ordering.

The reason is portability, not strictness: JavaScript reads a bare date as UTC
midnight and an offset-less timestamp as local time, while most other languages
read both as local. Accepting them would make the same feature flip at
different instants in different ports.

**R11.** The calendar components MUST be range-checked **before** parsing:
month 1–12, day 1 to the length of that month, leap years included, hour 0–23,
minute 0–59, second 0–60.

This is not redundant with a format check. Permissive parsers do not reject an
impossible date, they roll it over — JavaScript's `Date.parse` turns
`2027-02-30` into `2027-03-02`. A bound silently shifted by days is worse than
one that is ignored. Ports in languages with a strict parser still MUST reject
these values, so that every port ignores exactly the same set.

**R12.** A leap second (`:60`) is permitted by RFC 3339 but MUST be ignored,
because not every language can represent one. R11 lets second 60 through the
range check and this rule rejects it afterwards; the outcome is the same as any
other ignored bound.

**R13.** An offset MUST be applied, not stripped. `2026-09-18T14:00:00+02:00`
and `2026-09-18T12:00:00Z` are the same instant and MUST evaluate identically.

**R27.** Fractional seconds MUST be **truncated** to milliseconds — not
rounded, and not kept at a finer precision. `12:00:00.0009Z` is
`12:00:00.000Z`, and `12:00:00.9999Z` is `12:00:00.999Z`, not `12:00:01Z`.
Any number of digits MUST be accepted (R10), including more than nine.

JavaScript's `Date` holds milliseconds and `Date.parse` drops the rest. A port
that keeps nanoseconds flips a sub-millisecond bound up to a millisecond later
than the reference, and one that rounds flips it up to half a millisecond
early. Neither is visible in normal use; both are visible in a boundary case,
and the point of the suite is that no port has its own boundaries.

**R28.** An offset's hours MUST be `00`–`23` and its minutes `00`–`59`. Any
other offset makes the timestamp invalid, and it is then ignored under R8.
Within that range every offset MUST be applied (R13) — including offsets
beyond `±18:00`, which some date libraries (Java's `ZoneOffset`) cannot
represent and a port there has to compute itself. `-00:00` is the same
instant as `+00:00`.

This is the range JavaScript's `Date.parse` accepts. RFC 3339 does not bound
the offset itself, so without this rule each port would inherit whatever its
date library happens to allow.

## 4. Decorators

A port wraps a class and a method — or the nearest equivalent its language
offers. Evaluation timing is observable behaviour, so it is fixed here rather
than left to each port.

**R14.** A class-level toggle MUST be evaluated **once**, when the class is
decorated (loaded). A toggle changed afterwards MUST NOT affect an already
decorated class.

**R15.** A method-level toggle MUST be evaluated on **every call**. A toggle
changed after loading MUST affect the next call.

**R16.** If no provider is set, decorating MUST fail at decoration time, not at
the first call. In the reference this is a thrown
`"FeatureToggleProvider not set"`.

**R17.** Fallback behaviour:

| Target | Fallback | Toggle on | Toggle off |
|---|---|---|---|
| Method | none | original method | *nothing* |
| Method | method | original method | fallback, same arguments, same receiver |
| Class | none | original class | empty shell: every method returns *nothing* |
| Class | class | original class | fallback class |

*Nothing* is the language's empty result: `undefined`, `null`, `None`, or the
zero value.

**R18.** An asynchronous method on the empty shell MUST return an
already-resolved promise (or the language's equivalent), never a null value —
otherwise an `await` at the call site breaks.

**R19.** A fallback method MUST be invoked with the same arguments and the same
receiver as the original, so it can read the instance state the original would
have read.

## 5. Providers

A provider supplies feature data and answers `isEnabled`. Two shapes exist:

**R20.** *Feature shape* — the provider holds full feature records and MUST
delegate to the evaluation function of section 2. The time logic MUST live in
one place in the core, not be copied into each provider.

**R21.** *Boolean shape* — the provider holds plain booleans
(`{"myToggle": true}`) that map directly onto `isEnabled`. There is no time
logic here by design. A missing key MUST evaluate to `false`. The mapping cases
check this through `isEnabled`, not only through the stored data, because a
provider can hold the right data and still answer a missing key wrongly.

**R29.** In the boolean shape only the JSON boolean `true` is on. An entry
whose value is not a JSON boolean — the string `"true"`, the string
`"false"`, `1`, `null` — MUST be dropped when the data is loaded, and the key
then evaluates to `false` like any missing key. An entry holding the boolean
`false` MUST be kept, and evaluates to `false`.

This is R4 for the boolean shape: no coercion. A port that returns the stored
value and lets the caller test its truthiness turns `"false"` on, because a
non-empty string is truthy in JavaScript, Python and more. Dropping at load,
rather than only answering `false`, keeps the stored data identical across
ports, so the mapping cases can compare it.

## 6. Backend response mapping

Only relevant for a port with an API provider.

**R22.** `GET /features/:key` returns two different envelopes and a port MUST
read both:

- a single toggle as a flat object;
- a UUID group as `{"toggles": [...]}`.

A collection MAY also arrive under `value` instead of `toggles`; both MUST be
handled identically.

**R22a.** Field names are **lowercase** (`key`, `value`, `activeAt`,
`disabledAt`, `tags`) in both envelopes.

Backends before 0.1.7 spelled the group's fields capitalised (`Key`, `Value`,
`ActiveAt`, `DisabledAt`, `Tags`) while a single toggle came back lowercase,
because the DTO carried no JSON tags. That is fixed in the backend, but a port
cannot assume which version it is talking to, so it MUST accept either spelling
and normalise to the lowercase one. The capitalised spelling is legacy: a port
MUST NOT emit it and SHOULD NOT rely on it.

**R23.** Field normalisation MUST be by **presence**, not by truthiness. A
field that is present but empty (`"value": ""`, `"tags": []`) MUST be kept as
it is and MUST NOT fall through to another spelling or to a default. Choosing
with an `or`-style operator (`a.value || a.Value`) loses a legitimately falsy
value, which turns an off feature on.

**R24.** The backend returns unset dates as `null`; local fixtures commonly use
`""`. Both MUST normalise to "no bound" (R2).

**R25.** An entry without a usable key MUST be skipped rather than stored under
an empty key.

**R30.** A refresh of a port that fetches from the backend either succeeds as a
whole or fails as a whole:

- A body that is a group -- a collection envelope (R22), **even an empty one**,
  or a single toggle -- MUST replace the held data completely. Nothing is
  merged: a toggle absent from the new group is gone and evaluates to `false`.
  An empty group therefore switches every toggle of the group off; that is
  what deleting a group's last toggle looks like.
- A body that is not a group MUST fail the refresh and leave the held data
  exactly as it was: `null`, an array, any other non-object, an object with no
  collection envelope and no key (a proxy's error page, `{"error": ...}`), or a
  collection none of whose entries is usable (`{"toggles": [null]}`). Unusable
  entries next to usable ones are still just skipped (R25).

Both halves guard against the same silent failure in opposite directions.
Treating a garbage body as a group normalises it to nothing and switches every
feature off without an error; treating an empty group as a failure keeps a
deleted toggle on forever. A port that remembers the collection hash MUST
record it only after the group was applied, or a failed refresh is never
retried.

## 7. Backend agreement

**R26.** The backend flips scheduled toggles with a cron job that ticks about
once a minute, comparing against `now()`. A library that evaluates locally is
therefore up to a tick *ahead* of the backend's stored `value`. This is
intended: a port MUST evaluate the bounds itself and MUST NOT wait for the
backend's `value` to change.

**R31.** The backend MUST answer a group that exists but holds no toggles like
any other group: `GET /features/:uuid` with `200` and `{"toggles": []}`, and
`GET /collectionHash/:uuid` with `200` and the SHA-256 of the empty string
(`e3b0c442…b855`). Only the canonical, lowercase UUID names a group; a missing
single toggle and any other spelling of the UUID stay `404`.

Before backend 0.3.8 the empty group answered `404`. A port rightly reads that
as an outage and keeps its data (R30), so a group's deleted last toggle stayed
on in every client.

## Withdrawn rules

None.
