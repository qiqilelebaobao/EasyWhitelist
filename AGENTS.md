# EasyWhitelist — Agent Instructions

CLI tool that auto-detects the local public IP and syncs it to cloud security group whitelists (Tencent Cloud & Alibaba Cloud).

## Build & Test

```bash
pip install -e .        # install in editable mode
pytest tests/ -v        # run all tests
ew --help               # verify CLI entry point
```

Build backend: `flit_core` (PEP 517). CLI entry: `EasyWhitelist._core:main` → command `ew`.

## Architecture

```
EasyWhitelist/
  _core.py          # Entry point; app/DB init; dispatches to cloud provider
  detector/         # Detects public IP via multiple concurrent HTTP sources
  tcloud/           # Tencent Cloud: address templates, regions, security groups
  aliyun/           # Alibaba Cloud: prefix lists, regions, security groups
  config/           # CLI arg parsing (argparse), logging setup, global settings
  util/             # SQLite cache (db.py), app dir, CLI output helpers (cli.py)
```

Data flow: `CLI args → _core.py → cloud provider handler → IP detector → template/prefix update`

## Conventions

- **Typing**: full PEP 484; `from __future__ import annotations` in most files
- **Naming**: `snake_case` functions/variables, `SCREAMING_SNAKE_CASE` constants
- **Logging**: prefix module name in brackets — `logging.info("[template] ...")`
- **CLI output**: use helpers from `util/cli.py` — `echo_ok()`, `echo_err()`, `echo_progress()`, `echo_success()`
- **Error handling**: catch cloud SDK exceptions explicitly (e.g. `TencentCloudSDKException`); use `CreateResult` enum instead of magic numbers
- **Concurrency**: `ThreadPoolExecutor` for parallel IP detection and API calls; `tqdm` for progress display

## Cloud Credentials (env vars only — no config file)

| Provider | Variables |
|----------|-----------|
| Tencent Cloud (`-t`, default) | `TENCENTCLOUD_SECRET_ID`, `TENCENTCLOUD_SECRET_KEY` |
| Alibaba Cloud (`-a`) | `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET` |

Proxy support: `-p PORT` flag; `DISABLE_SSL_VERIFY=1` to skip SSL verification.

## Key Patterns

- **Multi-cloud abstraction**: Tencent and Alibaba modules mirror each other with matching `init/list/set` actions; unified dispatch in `_core.py`
- **SQLite caching**: regions and security groups are cached locally to speed up subsequent runs; implemented in `util/db.py`
- **IP deduplication**: `dict.fromkeys()` preserves order while removing duplicates

## Pitfalls

- Tests under `tests/l1/` and `tests/m1/` are module-level tests; run with `pytest tests/` to include all
- Do not hardcode credentials; always read from environment variables
- When adding a new cloud provider, mirror the existing `tcloud/` or `aliyun/` module structure and register in `_core.py`

See [README.md](README.md) for full usage examples and setup instructions.
