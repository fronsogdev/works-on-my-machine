## Image size comparison

`make build-compare` builds a deliberately naive single-stage image
(`docker/Dockerfile.naive`) and the real multi-stage API image
(`docker/Dockerfile.api`) from the same build context, then prints their size and
layer count.

The numbers below come from one run of that command on an `x86_64` machine with
Docker 29.9.0. They vary with CPU architecture and with the base-image digests
that are current at build time, so re-run the target rather than trusting these
figures on your platform.

| Image | Size | Layers | Why |
|---|---|---|---|
| `womm-api:latest` (real) | 353 MiB | 12 | multi-stage: `python:3.12-slim` runtime, locked venv, non-root, no build tools or caches |
| `womm-api:naive` | 1.7 GiB | 10 | single stage: full `python:3.12` base, unpinned `pip install`, runs as root |

The naive image is about **4.9× larger** (1,807,258,613 bytes vs. 370,166,921
bytes in that run). Two things drive almost all of the gap:

- **Base image.** The full `python:3.12` image carries a C compiler, development
  headers and build libraries that the application never needs once its
  dependencies are installed. The `-slim` runtime has none of that.
- **Packaging.** The naive image installs dependencies with plain `pip` and no
  lockfile, so the same commit can produce a different image tomorrow, and every
  build artifact stays in the one layer. The real image resolves the locked
  dependencies with `uv` in a builder stage and copies only the resulting virtual
  environment forward, so the compiler and the package cache never reach the
  final image.

Ownership and health are not visible in a size table but matter just as much: the
real image runs as uid 10001 on a read-only root filesystem with a tmpfs at
`/tmp`, and ships a `HEALTHCHECK`; the naive image does neither.
