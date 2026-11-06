# 🔓 Unauth-Checker

<div align="center">

**AI-Powered Unauthenticated API Endpoint Discovery Tool**

[![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Anthropic Claude](https://img.shields.io/badge/Powered%20by-Claude%20(Anthropic)-blueviolet.svg)](https://www.anthropic.com/)

*Automatically discover unauthenticated API endpoints using OpenAPI specifications and AI-generated test parameters*

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [How It Works](#-how-it-works)
- [Output Format](#-output-format)
- [Examples](#-examples)
- [Troubleshooting](#-troubleshooting)
- [Security & Ethics](#-security--ethics)
- [Contributing](#-contributing)

---

## 🎯 Overview

**Unauth-Checker** is an authorization-tier **differential** scanner. It doesn't
just ask "does this endpoint answer without auth?" — it compares each endpoint's
response across **unauthenticated**, **authenticated (user)**, and
**privileged (admin)** calls to separate real exposure from noise:

- 📥 Parses OpenAPI/Swagger (2.0 & 3.x) specifications
- 🤖 Optionally uses **Claude (Anthropic)** for realistic parameter values
  (reuses Claude Code's `~/.claude/settings.json`; or `--skip-ai-params` for
  spec-derived values with no key)
- 🔀 Fires each request across the active tiers and **compares responses**
  (normalized body similarity + sensitive-data detection) — not just status codes
- 🚦 **Adapts to rate limits** at runtime: reads limit headers, paces itself,
  and on `429/503` reads the cooldown, waits, and **re-runs** throttled requests
- 📊 Emits **signal, not noise** by default (a findings file with the real
  categories); the full per-call trace is opt-in via `--trace`

Perfect for security researchers, penetration testers, and developers auditing
API authorization.

---

## ✨ Features

### 🚀 Core Capabilities

- ✅ **OpenAPI 2.0 & 3.x Support** — works with Swagger and OpenAPI specs
- ✅ **Authorization-tier differential** — supply a user token (`-x`) and an
  admin token (`-a`); a finding is a *comparison across tiers*, so self-service
  endpoints and correctly-gated endpoints don't produce false positives
- ✅ **Verdict categories** — `AUTHZ-BYPASS`, `BFLA-PRIVESC` (privilege
  escalation), `OPEN-2XX-SENSITIVE`, `OPEN-2XX-REVIEW`, plus non-signal
  `PROTECTED` / `PUBLIC-LIKE` / `REDIRECT-LOGIN` / `UNVERIFIED-RATELIMITED`
- ✅ **Response-body similarity** — volatile fields (ids, timestamps) stripped,
  digit/hex runs collapsed, so the *same* resource compares as equal
- ✅ **Sensitive-data detection** — flags unauthenticated 2xx bodies containing
  emails, JWTs, API keys, SSN-like values
- ✅ **AI or spec-derived parameters** — Claude-generated values by default, or
  `--skip-ai-params` (OpenAPI `example`/`default`/`enum`, type heuristics) with
  no key required
- ✅ **Smart rate-limit management** — AIMD pacing, honors `RateLimit*`,
  `X-RateLimit-*` and `Retry-After` (delta *and* epoch), cools down on
  `429/503` and re-runs; a throttled request is **never** scored as `PROTECTED`
- ✅ **Signal-first output** — findings-only report by default; `--trace` for
  the complete per-call, per-tier log (CSV, and `.xlsx` if `openpyxl` present)

### 🎨 Also

- 🎯 **Verbose mode** (`-v`) for per-request debugging
- 🌐 **URL & file input** (`-u` / `-f`)
- 🧪 **Safe by default with admin creds** — when `-a` is set without
  `--methods`, the scan restricts to `GET,HEAD` to avoid mutating data
- ⚙️ **Tunable pacing/retries** (`--max-rps`, `--min-interval`, `--max-retries`,
  `--cooldown-cap`) and similarity threshold (`--similarity`)

---

## 📦 Prerequisites

Before installing Unauth-Checker, ensure you have:

- **Python 3.6+** installed on your system
- **Anthropic/Claude credentials** — the tool reuses the ones already configured
  for Claude Code in `~/.claude/settings.json` (no separate key needed). Only
  needed for AI parameter generation; use `--skip-ai-params` to run without them.
- **Internet connection** (for API calls and fetching OpenAPI specs)

---

## 🔧 Installation

### Step 1: Clone or Download

```bash
# If using git
git clone <repository-url>
cd unauth-checker

# Or download and extract the files
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

- `requests` — required
- `openpyxl` — optional; enables the `.xlsx` `--trace` output
- `pytest` — only needed to run the test suite

### Step 3: Credentials

**No separate API key setup is required.** The parameter-generation agent reads
the Anthropic credentials already configured for Claude Code from
`~/.claude/settings.json` (the `env` block: `ANTHROPIC_AUTH_TOKEN`,
`ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`).

You can still override via environment variables if you prefer:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."        # or ANTHROPIC_AUTH_TOKEN
export ANTHROPIC_BASE_URL="https://api.anthropic.com"   # optional
export ANTHROPIC_MODEL="claude-sonnet-5"                # optional
```

**Or skip AI entirely** (no key of any kind) with `--skip-ai-params`:

```bash
python3 unauth_checker.py -u https://api.example.com/openapi.json --skip-ai-params
```

In this mode values come from the OpenAPI spec itself (`example` / `default` /
`enum`) or from type-based fallbacks — only the core checker runs, `ai_agent.py`
is never called.

### Step 4: Verify Installation

```bash
python3 unauth_checker.py --help
```

You should see the help menu. If you get an error about missing credentials, either configure Claude Code's `~/.claude/settings.json` or pass `--skip-ai-params`.

---

## ⚙️ Configuration

### AI Provider (Claude / Anthropic)

The parameter-generation agent (`ai_agent.py`) uses the Anthropic **Messages
API** (`/v1/messages`). Credentials are resolved in this order:

1. Environment variables (`ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY`)
2. The `env` block in `~/.claude/settings.json` (what Claude Code uses)
3. Defaults

- **Base URL:** `ANTHROPIC_BASE_URL`, defaulting to `https://api.anthropic.com`
  (works transparently with a Claude Code gateway/proxy).
- **Model:** `ANTHROPIC_MODEL`.
- **Auth header:** `Authorization: Bearer` for custom gateways, `x-api-key`
  for `api.anthropic.com`.

If no credentials are found the tool errors with a clear message — or bypass AI
altogether with `--skip-ai-params`.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY` | For AI mode | Claude/Anthropic key (falls back to `~/.claude/settings.json`) |
| `ANTHROPIC_BASE_URL` | ❌ No | Override API base URL |
| `ANTHROPIC_MODEL` | ❌ No | Override model name |

---

## 🚀 Usage

### Basic Usage

**Scan from OpenAPI URL:**
```bash
python3 unauth_checker.py -u https://api.example.com/openapi.json
```

**Scan from Local File:**
```bash
python3 unauth_checker.py -f /path/to/openapi.json
```

### Advanced Usage

**Full differential scan (unauth + user + admin):**
```bash
python3 unauth_checker.py \
  -u https://api.example.com/openapi.json \
  -x "Authorization: Bearer <USER_TOKEN>" \
  -a "Authorization: Bearer <ADMIN_TOKEN>" \
  --skip-ai-params -v
```

**Single-tier (unauth only), custom output + full trace:**
```bash
python3 unauth_checker.py -f ./openapi.json -o my-results --trace
```

### Command-Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--url` | `-u` | URL to OpenAPI JSON specification (one of `-u`/`-f`) |
| `--file` | `-f` | Path to local OpenAPI JSON file (one of `-u`/`-f`) |
| `--output` | `-o` | Base output name (findings/trace derive from it; else auto-named from host) |
| `--verbose` | `-v` | Show detailed execution logs |
| `--skip-ai-params` | — | Skip AI (`ai_agent.py`) generation; use spec/type values, no API key |
| `--user-header` | `-x` | Authenticated (user-tier) header, e.g. `-x "Authorization: Bearer …"`. Repeatable; full `Name: value` or bare token |
| `--admin-header` | `-a` | Privileged (admin-tier) header, compared with the user tier for BFLA. Repeatable |
| `--methods` | — | Comma-separated methods (e.g. `get,post`). Defaults to `get,head` when `-a` is set |
| `--trace` | — | Also write the full per-call/per-tier log (CSV, and `.xlsx` if openpyxl) |
| `--similarity` | — | Body-similarity threshold for "same data" (default `0.90`) |
| `--max-rps` | — | Hard ceiling on requests/sec per host (default `5`) |
| `--min-interval` | — | Minimum seconds between requests per host (default `0.05`) |
| `--max-retries` | — | Per-request retry budget when rate-limited (default `4`) |
| `--cooldown-cap` | — | Max seconds to sleep for a single cooldown (default `120`) |

> `-x`/`-a` accept a full header (`X-API-Key: abc`, `Cookie: a=1; b=2`) or a
> bare token (`eyJ…` / `Bearer …` / `Token …` → sent as `Authorization`).

---

## 🔍 How It Works

### Workflow

```
 OpenAPI Spec ──▶ Extract endpoints & params ──▶ generate param values
                                                   (Claude or spec/type)
        │
        ▼
 For each (endpoint, method, param-set):
        │   fire at every ACTIVE tier
        ├──▶ unauth      ─┐
        ├──▶ user  (-x)   ├──▶ normalize bodies, compare similarity,
        └──▶ admin (-a)   ┘    detect sensitive data
        │
        ▼
   decision matrix  ──▶  Verdict (AUTHZ-BYPASS / BFLA-PRIVESC / OPEN-2XX-… /
                                  PROTECTED / PUBLIC-LIKE / UNVERIFIED-…)
        │
        ▼
   findings-only report (signal);  --trace  ──▶ full per-call log
```

Every request goes through `SafeHTTP`, which reads rate-limit headers, paces
itself, and on `429/503` waits the advertised cooldown and re-runs — so a
throttled response never masquerades as a result.

### Detailed Process

1. **Load spec** — fetch URL or read file; base URL from `servers` (3.x) or
   `host` (2.0).
2. **Extract endpoints** — paths, methods, parameters (`in` = path/query/header/
   cookie), and request-body examples.
3. **Parameter values** — Claude-generated (default), or with
   `--skip-ai-params`, spec `example`/`default`/`enum` with type heuristics.
   Parameterless endpoints send exactly one request (no duplicate empty call).
4. **Probe across tiers** — each request is sent as unauthenticated, and again
   with the `-x` user header(s) and `-a` admin header(s) when provided. Bodies
   are normalized (volatile ids/timestamps dropped, digit/hex runs collapsed).
5. **Decide** — the cross-tier matrix (below) turns the probe set into a verdict;
   a *separate* BFLA check flags a normal user reaching admin-scoped data.
6. **Report** — signal findings written; noise suppressed unless `--trace`.

### Decision Matrix

| Situation (unauth → user → admin) | Verdict | Signal? |
|---|---|---|
| unauth 2xx **and** user 2xx, bodies ≈ identical | `AUTHZ-BYPASS` (90, High) | ✅ |
| unauth **rejected**, admin-scoped route, user ≈ admin | `BFLA-PRIVESC` (88, High) | ✅ |
| unauth 2xx, sensitive-looking body, no user tier | `OPEN-2XX-SENSITIVE` (80, High) | ✅ |
| unauth 2xx, ambiguous vs user tier | `OPEN-2XX-REVIEW` (55, Medium) | ✅ |
| unauth 2xx but body clearly differs from user's | `PUBLIC-LIKE` (20) | ❌ |
| unauth 401/403 | `PROTECTED` (0) | ❌ |
| unauth 3xx / generic 4xx / 5xx | `REDIRECT-LOGIN` / `REACHABLE-NO-DATA` / `SERVER-ERROR` | ❌ |
| rate-limited, retries exhausted | `UNVERIFIED-RATELIMITED` (0) | ❌ |

BFLA deliberately requires **both** a real privilege boundary (unauth rejected)
and a privileged endpoint scope, so self-service endpoints (where a normal user
and an admin legitimately see the same thing) are *not* flagged.

---

## 📄 Output Format

### Findings (default) — `<output>.findings.csv`

Signal categories only; protected/non-signal rows are suppressed.

| Column | Description |
|--------|-------------|
| `category` | `AUTHZ-BYPASS`, `BFLA-PRIVESC`, `OPEN-2XX-SENSITIVE`, `OPEN-2XX-REVIEW` |
| `confidence` | 0–100 |
| `level` | High / Medium / Low / Inconclusive |
| `endpoint`, `method` | the affected route |
| `params_values` | parameter set that produced it |
| `tiers` | per-tier status, e.g. `unauth=401,user=200,admin=200` |
| `similarity` | body-similarity when the verdict is comparison-based |
| `evidence` | human-readable justification |

A console summary reports SIGNAL / NOISE / UNVERIFIED counts and the number of
rate-limit throttles hit and re-runs performed.

### Trace (opt-in) — `<output>.trace.csv` (+ `.xlsx`)

`--trace` writes **every** request at **every** tier (`endpoint, method, tier,
params_values, status, body_len, attempt, error`) for full auditability, plus a
formatted workbook when `openpyxl` is installed.

### File Naming

If `-o` is omitted, output is auto-named from the target host (e.g.
`api-example-com.findings.csv`). Confidence levels: **High** ≥ 80, **Medium**
≥ 50, **Low** ≥ 20, else **Inconclusive**.

---

## 💡 Examples

### Example 1: Three-tier differential scan

```bash
$ python3 unauth_checker.py -u https://api.example.com/openapi.json \
      -x "Authorization: Bearer $USER_TOKEN" \
      -a "Authorization: Bearer $ADMIN_TOKEN" \
      --skip-ai-params

============================================================
SIGNAL:  2 AUTHZ-BYPASS   1 BFLA-PRIVESC   1 OPEN-2XX-SENSITIVE
NOISE:   138 protected / non-signal (suppressed)
RATE-LIMITS: 3 throttle hit(s), 3 re-run(s)
VERDICTS: 145 total
Findings -> api-example-com.findings.csv
============================================================
```

The findings file lists only the exposure, with the tier evidence:

```csv
category,confidence,level,endpoint,method,params_values,tiers,similarity,evidence
AUTHZ-BYPASS,90,High,/api/v1/reports,GET,{},"unauth=200,user=200,admin=200",1.00,unauth 200 == user 200 (sim 1.00)
BFLA-PRIVESC,88,High,/api/v1/admin/users,GET,{},"unauth=401,user=200,admin=200",1.00,unauth 401 but user 200 == admin 200 (sim 1.00)
OPEN-2XX-SENSITIVE,80,High,/api/v1/master/enums,GET,{},"unauth=200","email/JWT/key" ,unauth 2xx with sensitive-looking body
```

### Example 2: Full trace on request

Adding `--trace` keeps the findings file *and* writes every call:

```bash
$ python3 unauth_checker.py -f ./openapi.json --trace -o audit
```
```csv
endpoint,method,tier,params_values,status,body_len,attempt,error
/api/v1/admin/users,GET,unauth,{},401,22,0,
/api/v1/admin/users,GET,user,{},200,512,0,
/api/v1/admin/users,GET,admin,{},200,512,0,
/api/v1/reports,GET,unauth,{},429,0,0,            # throttled …
/api/v1/reports,GET,unauth,{},200,880,2,           # … re-run after cooldown
```

---

## 🔧 Troubleshooting

### Common Issues

#### ❌ `No Anthropic API key found`

**Solution:**
Configure Claude Code (`~/.claude/settings.json`) or `export ANTHROPIC_API_KEY=...`. Or run with `--skip-ai-params` to bypass AI entirely.

#### ❌ `Failed to fetch OpenAPI spec from URL`

**Possible Causes:**
- Network connectivity issues
- Invalid URL
- Server requires authentication

**Solution:**
- Check internet connection
- Verify URL is accessible
- Try downloading the spec manually and use `-f` flag

#### ❌ `No base URL found in OpenAPI spec`

**Solution:**
- Ensure OpenAPI spec has `servers` field (OpenAPI 3.0+) or `host` field (OpenAPI 2.0)
- Use `-u` flag instead of `-f` to auto-detect base URL from URL

#### ❌ AI API calls failing

**Possible Causes:**
- Invalid API key
- Rate limiting
- Network issues

**Solution:**
- Verify API key is correct
- Check the Anthropic/gateway service status
- Tool will fallback to "test" values if AI fails

#### ❌ No findings file / trace file created

**Solution:**
- Check write permissions in the current directory and available disk space
- The findings file is always written; the `.trace.csv` / `.xlsx` only appear
  with `--trace`
- For the `.xlsx` trace, ensure `openpyxl` is installed: `pip install openpyxl`

#### ❌ Too few / too many "protected" results

**Solution:**
- A single unauthenticated `200` is only `OPEN-2XX-REVIEW`. Supply a user token
  (`-x`) to promote a real exposure to `AUTHZ-BYPASS`, and an admin token (`-a`)
  to enable the `BFLA-PRIVESC` check.
- Tune `--similarity` if bodies for the same resource are scored as different
  (raise it) or different resources look alike (lower it).

#### ❌ Many `UNVERIFIED-RATELIMITED` results

**Solution:**
- The target throttled the scanner and retries were exhausted. Lower `--max-rps`,
  raise `--max-retries` / `--cooldown-cap`, and re-run — these are never counted
  as protected, so they need a clean retry to become a verdict.

---

## 🛡️ Security & Ethics

### ⚠️ Important Disclaimer

**This tool is for authorized security testing only.**

### Ethical Guidelines

- ✅ **Always obtain written permission** before testing any API
- ✅ **Only test APIs you own** or have explicit authorization to test
- ✅ **Respect rate limits** and don't overload target servers
- ✅ **Report vulnerabilities responsibly** through proper channels
- ❌ **Never use this tool** on systems you don't have permission to test
- ❌ **Don't use for malicious purposes** or unauthorized access

### Legal Notice

Unauthorized access to computer systems is illegal in most jurisdictions. The authors and contributors of this tool are not responsible for any misuse or damage caused by this tool.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### How to Contribute

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

---

## 🙏 Acknowledgments

- **Anthropic Claude** for providing the AI API for parameter generation
- OpenAPI/Swagger community for the specification standards
- All contributors and users of this tool

---

## 📞 Support & Contact

For issues, questions, or suggestions:

- 🐛 **Bug Reports:** Open an issue on GitHub
- 💬 **Questions:** Check existing issues or open a new one
- ⭐ **Show Support:** Star the repository if you find it useful!
- 💼 **LinkedIn:** [Yash Prajapati](https://www.linkedin.com/in/yash-prajapati-791m18104/)

---

<div align="center">

**Made with ❤️ for the security community**

⭐ **Star this repo if you find it helpful!** ⭐

</div>
