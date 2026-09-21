#!/usr/bin/env bash
#
# Fetches the YaFT conformance suite pinned in conformance.lock.
#
# Copy this into a port, next to a conformance.lock of the form:
#
#   version=v1.0.0
#   sha256=<checksum of cases.tar.gz>
#
# The checksum is not optional. A Git tag can be moved; verifying the asset is
# what stops a port's tests from changing without a diff.
#
# Usage: scripts/fetch-conformance.sh [target-dir]   (default: test/conformance)

set -euo pipefail

REPO="tehw0lf/yaft-conformance"
LOCK="${LOCK:-conformance.lock}"
TARGET="${1:-test/conformance}"

if [[ ! -f "$LOCK" ]]; then
  echo "error: $LOCK not found; run from the port's root" >&2
  exit 1
fi

version="$(grep -E '^version=' "$LOCK" | cut -d= -f2-)"
expected="$(grep -E '^sha256=' "$LOCK" | cut -d= -f2-)"

if [[ -z "$version" || -z "$expected" ]]; then
  echo "error: $LOCK needs both version= and sha256=" >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

url="https://github.com/${REPO}/releases/download/${version}/cases.tar.gz"
echo "fetching conformance suite ${version}"
curl --fail --location --silent --show-error --output "$tmp/cases.tar.gz" "$url"

actual="$(sha256sum "$tmp/cases.tar.gz" | cut -d' ' -f1)"
if [[ "$actual" != "$expected" ]]; then
  echo "error: checksum mismatch for cases.tar.gz" >&2
  echo "  expected $expected" >&2
  echo "  actual   $actual" >&2
  echo "The tag may have been moved. Do not update the lock without reading the diff." >&2
  exit 1
fi

rm -rf "$TARGET"
mkdir -p "$TARGET"
tar --extract --gzip --file "$tmp/cases.tar.gz" --directory "$TARGET"

echo "conformance suite ${version} unpacked into ${TARGET}"
