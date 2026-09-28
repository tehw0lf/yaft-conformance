#!/usr/bin/env python3
"""Checks the case files against SPEC.md.

The JSON schema checks the shape of a case. This checks the things a schema
cannot: that every `rule` reference points at a rule that exists, that every
rule in SPEC.md is actually exercised by at least one case, and that case names
are unique within a file.

The second check is the important one. A rule nobody tests is a rule ports can
quietly ignore, which is the failure mode this repo exists to prevent.
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Rules that are stated for completeness but have no case of their own, with
# the reason. Anything not listed here must be covered.
UNTESTED = {
    "R1": "a property of the data model; every value case depends on it",
    "R9": "structural -- a port without an injectable clock cannot run the suite at all",
    "R20": "structural -- asserted by the evaluation suite running through the provider",
    "R26": "backend timing; covered by the Go backend's integration tests, not by data",
    "R31": "a backend obligation; covered by the Go backend's integration tests, not by data",
}


def _rule_order(rule: str) -> tuple[int, str]:
    """Sorts R9 before R10, and R22 before R22a."""
    match = re.fullmatch(r"R(\d+)([a-z]?)", rule)
    return (int(match.group(1)), match.group(2)) if match else (0, rule)


def spec_rules() -> tuple[set[str], set[str]]:
    text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    withdrawn = set()
    defined = set()
    for match in re.finditer(r"\*\*(R\d+[a-z]?)\.\*\*", text):
        defined.add(match.group(1))
    for match in re.finditer(r"\*\*(R\d+[a-z]?)\.\*\*[^\n]*withdrawn", text, re.IGNORECASE):
        withdrawn.add(match.group(1))
    # The rule table in section 4 states R17 in a table rather than a sentence;
    # any rule mentioned in a heading-level bold marker is picked up above.
    return defined, withdrawn


def main() -> int:
    errors: list[str] = []
    defined, withdrawn = spec_rules()

    if not defined:
        print("error: no rules found in SPEC.md", file=sys.stderr)
        return 1

    referenced: set[str] = set()

    for path in sorted((ROOT / "cases").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        names: set[str] = set()

        for case in data["cases"]:
            name = case["name"]
            if name in names:
                errors.append(f"{path.name}: duplicate case name {name!r}")
            names.add(name)

            for rule in case["rules"]:
                referenced.add(rule)
                if rule not in defined:
                    errors.append(
                        f"{path.name}: case {name!r} references {rule}, "
                        "which is not defined in SPEC.md"
                    )
                elif rule in withdrawn:
                    errors.append(
                        f"{path.name}: case {name!r} references {rule}, which is withdrawn"
                    )

    uncovered = defined - withdrawn - referenced - set(UNTESTED)
    for rule in sorted(uncovered, key=_rule_order):
        errors.append(
            f"SPEC.md: {rule} has no case. Add one, or list it in UNTESTED "
            "with a reason."
        )

    stale = set(UNTESTED) & referenced
    for rule in sorted(stale, key=_rule_order):
        errors.append(
            f"scripts/validate-cases.py: {rule} is listed as untested but now has "
            "a case; remove it from UNTESTED."
        )

    missing = set(UNTESTED) - defined
    for rule in sorted(missing, key=_rule_order):
        errors.append(
            f"scripts/validate-cases.py: UNTESTED lists {rule}, which SPEC.md "
            "does not define."
        )

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        f"ok: {len(defined)} rules, "
        f"{len(referenced)} covered by cases, "
        f"{len(UNTESTED)} structural, "
        f"{len(withdrawn)} withdrawn"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
