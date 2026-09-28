<p align="center"><img src="logo.svg" width="120" alt="YaFT"></p>

# yaft-conformance

The rules of [YaFT](https://github.com/tehw0lf/yaft) written down once, as prose
and as data, so that every implementation answers the same questions the same
way.

- [`SPEC.md`](SPEC.md) — the normative rules, numbered `R1`, `R2`, …
- [`cases/`](cases) — machine-readable cases, each pointing at the rules it pins
  down
- [`schema/case.schema.json`](schema/case.schema.json) — the shape of a case file
- [`VERSION`](VERSION) — the suite version that ports pin

A port is conformant when it passes every case. There is no partial credit and
no per-port exception list: if a case is wrong, the case gets fixed here, for
everyone.

## The case files

| File | Covers |
|---|---|
| `cases/evaluation.json` | `isEnabled` — value, time bounds, timestamp parsing |
| `cases/decorator.json` | class and method toggles, fallbacks, evaluation timing |
| `cases/mapping.json` | normalising backend responses and the boolean shape |

Every evaluation case carries its own `now`:

```json
{
  "name": "active-at-boundary",
  "rules": ["R5"],
  "why": "The comparison is now < activeAt, so the boundary itself is on.",
  "now": "2026-09-18T12:00:00Z",
  "features": {
    "f": { "key": "f", "value": "true", "activeAt": "2026-09-18T12:00:00Z", "disabledAt": "" }
  },
  "key": "f",
  "expected": true
}
```

That is deliberate. Time-dependent behaviour is only testable if the clock can
be set, so the suite forces every port to make its clock injectable (`R9`).

The `decorator` and `mapping` cases cannot be pure input/output pairs, because
"the fallback receives the same receiver" is not something JSON can express.
They instead name a scenario and an outcome in port-neutral terms — `original`,
`fallback`, `nothing`, `empty-shell`, `decoration-error` — and each adapter maps
those onto its own language's constructs.

## Wiring a port to the suite

The suite ships as a release asset rather than a submodule, so toolchains like
Maven or `go test` need no Git handling.

**1. Pin a version.** Add a `conformance.lock` to the port:

```
version=v1.0.0
sha256=<checksum of cases.tar.gz>
```

The checksum is mandatory. A tag can be moved; without a checksum that would
change a port's tests silently. A suite bump is then a one-line diff that a
reviewer sees.

The asset is built reproducibly, so the checksum can be confirmed from the tag
rather than taken on trust:

```sh
git clone --branch v1.0.0 --depth 1 https://github.com/tehw0lf/yaft-conformance
cd yaft-conformance
tar --create --gzip --file - --sort=name --owner=0 --group=0 --numeric-owner \
    --mode='u=rwX,go=rX' --mtime='UTC 2020-01-01' \
    cases schema SPEC.md VERSION | sha256sum
```

`--mode` is not decoration. Without it the archive carries whatever permission
bits the checkout happened to have, and the same content yields a different
checksum under a different umask.

**2. Fetch before testing.** Copy
[`scripts/fetch-conformance.sh`](scripts/fetch-conformance.sh) into the port,
have it unpack into `test/conformance/`, and gitignore that directory.

**3. Write the adapter.** One test per suite that loads the cases, builds a
provider from `features`, injects `now`, and asserts `expected`. In TypeScript
an evaluation case is simply:

```ts
expect(evaluate(c.features[c.key], Date.parse(c.now))).toBe(c.expected);
```

**4. Run it in CI**, before the port's own tests.

The adapter must fail loudly if a case file contains a `suite`, `target`,
`toggle` or `expected` value it does not know. A skipped unknown case is a
silently unenforced rule — the one failure mode this whole repo exists to
prevent.

For the same reason the adapter must check each file's format `version` and
reject one it does not know. A new field is invisible to an adapter that never
reads it; the format version is what makes it visible. Current formats:
`evaluation` 1, `decorator` 1, `mapping` 3 (since 2.0.0: boolean-shape cases
carry an `isEnabled` map of keys to ask and the answer each must give; since
3.0.0: feature-shape cases may carry `held`, the data the provider holds before
`response` arrives).

A case with `held` tests a refresh, not a pure mapping (R30), so it has to run
through the port's real API provider: serve `held` as a group from a stub
backend and refresh, then serve `response` under a new collection hash and
refresh again, and compare the provider's data with `expected`. The second
refresh fails for a body that is not a group; the adapter expects that failure
and still compares, because keeping `held` is the point.

## Changing the suite

- A new rule gets the next free number. Numbers are never reused and never
  renumbered; a retired rule stays in `SPEC.md` marked withdrawn.
- A case that changes an expectation is a breaking change: bump the major in
  `VERSION`, because ports pin it and will need work.
- Adding cases that only pin down existing rules is a minor bump. So is a new
  rule that writes down what the reference already does, like R27 and R28.
- A new rule that an existing port fails is a major bump, like any other
  change that leaves ports with work to do: R29 made 2.0.0, R30 and the
  `held` field made 3.0.0.
- A new or changed field in a case bumps that file's format `version`.
- Every case carries the rules it covers, and a `why` wherever the expectation
  is not self-evident.

## License

MIT
