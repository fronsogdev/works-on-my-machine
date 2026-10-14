#!/bin/sh
# Build the deliberately naive API image and the real API image from the same
# build context, then print a side-by-side comparison of size and layer count.
#
# Invoked by `make build-compare`. It exits non-zero if Docker is unavailable or
# if either build fails, so the target never reports success on a broken build.
# Sizes and layer counts are read from the built images, not hard-coded, so the
# numbers reflect this machine's architecture and base-image digests.

set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

NAIVE_TAG="womm-api:naive"
REAL_TAG="womm-api:latest"
CONTEXT="."

if ! command -v docker >/dev/null 2>&1; then
    echo "error: docker is not installed or not on PATH" >&2
    exit 1
fi

echo "==> Building real image ($REAL_TAG)"
if ! docker build -f docker/Dockerfile.api -t "$REAL_TAG" "$CONTEXT"; then
    echo "error: failed to build $REAL_TAG" >&2
    exit 1
fi

echo "==> Building naive image ($NAIVE_TAG)"
if ! docker build -f docker/Dockerfile.naive -t "$NAIVE_TAG" "$CONTEXT"; then
    echo "error: failed to build $NAIVE_TAG" >&2
    exit 1
fi

size_bytes() {
    docker image inspect "$1" --format '{{.Size}}'
}

layer_count() {
    docker image inspect "$1" --format '{{len .RootFS.Layers}}'
}

human_size() {
    awk -v bytes="$1" 'BEGIN {
        split("B KiB MiB GiB TiB", unit, " ")
        i = 1
        while (bytes >= 1024 && i < 5) { bytes /= 1024; i++ }
        if (i == 1) { printf "%.0f %s", bytes, unit[i] } else { printf "%.1f %s", bytes, unit[i] }
    }'
}

REAL_BYTES=$(size_bytes "$REAL_TAG")
NAIVE_BYTES=$(size_bytes "$NAIVE_TAG")
REAL_LAYERS=$(layer_count "$REAL_TAG")
NAIVE_LAYERS=$(layer_count "$NAIVE_TAG")
REAL_SIZE=$(human_size "$REAL_BYTES")
NAIVE_SIZE=$(human_size "$NAIVE_BYTES")
RATIO=$(awk -v a="$NAIVE_BYTES" -v b="$REAL_BYTES" 'BEGIN { printf "%.2f", a / b }')

REAL_WHY="multi-stage, slim base, locked venv, non-root, no caches"
NAIVE_WHY="single stage, full base, unpinned pip, root, no lockfile"

printf '\n'
printf '%-16s  %-10s  %6s  %s\n' "IMAGE" "SIZE" "LAYERS" "WHY"
printf '%-16s  %-10s  %6s  %s\n' "----------------" "----------" "------" "----------------------------------------------"
printf '%-16s  %-10s  %6s  %s\n' "$REAL_TAG" "$REAL_SIZE" "$REAL_LAYERS" "$REAL_WHY"
printf '%-16s  %-10s  %6s  %s\n' "$NAIVE_TAG" "$NAIVE_SIZE" "$NAIVE_LAYERS" "$NAIVE_WHY"
printf '\n'
printf 'The naive image is %sx the size of the real one (%s vs %s bytes).\n' \
    "$RATIO" "$NAIVE_BYTES" "$REAL_BYTES"
printf 'Sizes and layer counts depend on CPU architecture and the base image digests.\n'
