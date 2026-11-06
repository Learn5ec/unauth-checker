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

**Unauth-Checker** is an intelligent security testing tool that automatically identifies unauthenticated API endpoints by:

- 📥 Parsing OpenAPI/Swagger specifications
- 🤖 Using **Claude (Anthropic)** to generate realistic parameter values
- 🧪 Testing endpoints with multiple parameter combinations
- 📊 Generating detailed CSV reports with response analysis

Perfect for security researchers, penetration testers, and developers who need to audit API security.

---

## ✨ Features

### 🚀 Core Capabilities

- ✅ **OpenAPI 2.0 & 3.0+ Support** - Works with both Swagger and OpenAPI specifications
- ✅ **AI-Powered Parameter Generation** - Uses Claude (Anthropic) to create realistic test values (or `--skip-ai-params` for spec-derived values with no key)
- ✅ **Triple Testing Strategy** - Tests each endpoint with:
  - Empty parameters
  - First AI-generated parameter set
  - Second AI-generated parameter set
- ✅ **Resume Capability** - Automatically resumes interrupted scans
- ✅ **Smart File Versioning** - Auto-generates versioned output files (e.g., `api.example.com.csv`, `api.example.com1.csv`)
- ✅ **Progress Tracking** - Real-time progress bar with detailed statistics
- ✅ **Comprehensive CSV & Excel Reports** - Includes:
  - Endpoint paths and HTTP methods
  - Parameter counts and values used
  - HTTP status codes received
  - Full response bodies (up to 2000 characters)
  - Confidence scores
  - Detailed notes
  - **Real-time updates** - Both CSV and Excel files update as scan progresses

### 🎨 Additional Features

- 🔄 **Real-time Updates** - Both CSV and Excel files update incrementally as scan progresses
- 📊 **Professional Excel Formatting** - Auto-generated Excel files with optimized column widths, row heights, and alignment
- 📈 **Confidence Scoring** - Automatic risk assessment (0-100 scale)
- 🎯 **Verbose Mode** - Detailed execution logs for debugging
- 🌐 **URL & File Input** - Support for remote URLs and local files
- ⚡ **Error Handling** - Graceful failure recovery with fallback mechanisms
- 🔁 **Resume Support** - Automatically resumes from where it left off if scan is interrupted

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

**Required:**
```bash
pip install requests
```

**Optional (for Excel output with formatting):**
```bash
pip install openpyxl
```

Or using `pip3`:

```bash
pip3 install requests
pip3 install openpyxl  # Optional, for Excel formatting
```

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

**With Custom Output File:**
```bash
python3 unauth_checker.py -u https://api.example.com/openapi.json -o my-results.csv
```

**With Verbose Output:**
```bash
python3 unauth_checker.py -u https://api.example.com/openapi.json -v
```

**Complete Example:**
```bash
python3 unauth_checker.py \
  -u https://api.example.com/openapi.json \
  -o security-audit-results.csv \
  -v
```

### Command-Line Options

| Option | Short | Description | Required |
|--------|-------|-------------|----------|
| `--url` | `-u` | URL to OpenAPI JSON specification | ⚠️ One of `-u` or `-f` |
| `--file` | `-f` | Path to local OpenAPI JSON file | ⚠️ One of `-u` or `-f` |
| `--output` | `-o` | Custom output CSV filename | ❌ No (auto-generated) |
| `--verbose` | `-v` | Show detailed execution logs | ❌ No |
| `--skip-ai-params` | — | Skip AI (`ai_agent.py`) param generation; use spec/type values, no API key | ❌ No |

---

## 🔍 How It Works

### Workflow Diagram

```
┌─────────────────┐
│  OpenAPI Spec   │
│  (URL or File)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extract Endpoints│
│  & Parameters   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  For Each       │─────▶│  Claude AI   │
│  Parameter      │      │  Generate    │
│                 │      │  Test Values │
└────────┬────────┘      └──────────────┘
         │
         ▼
┌─────────────────┐
│  Test Endpoint  │
│  3 Times:       │
│  • Empty params │
│  • Set 1        │
│  • Set 2        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Save Results   │
│  to CSV         │
└─────────────────┘
```

### Detailed Process

1. **📥 Load OpenAPI Specification**
   - Fetches from URL or reads from local file
   - Extracts base URL from `servers` field (OpenAPI 3.0+) or `host` field (OpenAPI 2.0)

2. **🔎 Extract Endpoints**
   - Parses all paths and HTTP methods
   - Extracts parameter definitions (name, type, description)

3. **🤖 AI Parameter Generation**
   - For each parameter, sends request to Claude (Anthropic) with:
     - Parameter name
     - Parameter type
     - Parameter description
   - Generates 2 sets of realistic test values

4. **🧪 Endpoint Testing**
   - Tests each endpoint 3 times:
     - **Test 1:** Empty parameters `{}`
     - **Test 2:** First AI-generated parameter set
     - **Test 3:** Second AI-generated parameter set
   - Captures HTTP status codes and response bodies

5. **📊 Result Analysis**
   - Calculates confidence scores (0-100)
   - Categorizes results (High/Medium/Low/Inconclusive)
   - Saves to CSV with all details

6. **💾 Output Generation**
   - Creates both CSV and Excel files (if openpyxl installed)
   - Hostname-based automatic file naming
   - Auto-versions files if they already exist (e.g., `hostname.csv`, `hostname1.csv`)
   - Real-time incremental writing (both CSV and Excel update as scan progresses)
   - Resume capability - tracks completed test cases to avoid duplicates

---

## 📄 Output Format

### CSV Structure

The generated CSV file contains the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| `endpoint` | API endpoint path | `/api/users` |
| `method` | HTTP method | `GET`, `POST`, etc. |
| `params_count` | Number of parameters | `3` |
| `params_values` | JSON string of parameter values | `{"id": "123", "name": "test"}` |
| `status_codes` | HTTP status code(s) received | `200`, `401,403` |
| `response` | Response body (truncated to 2000 chars) | `{"status": "success"}` |
| `confidence` | Confidence score (0-100) | `60` |
| `confidence_level` | Risk category | `Medium`, `High`, etc. |
| `notes` | Test case information | `Test case: set_1` |

### File Naming

- **Auto-generated:** `{hostname}.csv` and `{hostname}.xlsx` (if openpyxl is installed)
  - Example: `api-example-com.csv` and `api-example-com.xlsx`
- **Versioned:** If file exists, creates `{hostname}1.csv`, `{hostname}2.csv`, etc.
- **Custom:** Use `-o` flag to specify custom filename

### Excel Formatting (Optional)

If `openpyxl` is installed, the tool automatically generates an Excel file (`.xlsx`) alongside the CSV with professional formatting:

- ✅ **Optimized Column Widths** - Precisely sized in centimeters for readability
- ✅ **Formatted Headers** - Bold white text on blue background, top-aligned
- ✅ **Text Wrapping** - Long content (responses, parameters) wrap automatically
- ✅ **Custom Row Heights** - Header row: 0.7 cm, Data rows: 3.85 cm
- ✅ **Smart Alignment** - Left/center alignment based on column type, response column top-aligned
- ✅ **Real-time Updates** - Excel file saves after each row (just like CSV)
- ✅ **Professional Styling** - Ready for presentations and reports

**Column Widths (in cm):**
- Endpoint: 4.7 cm (left-aligned)
- Method: 2.5 cm (center-aligned)
- Params Count: 3.55 cm (center-aligned)
- Params Values: 5.0 cm (left-aligned, wrapped)
- Status Codes: 3.25 cm (center-aligned)
- Response: 11.5 cm (left-aligned, top-aligned, wrapped)
- Confidence: 2.9 cm (center-aligned)
- Confidence Level: 4.2 cm (center-aligned)
- Notes: 5.5 cm (center-aligned in header, left-aligned in data)

**Row Heights:**
- Header Row: 0.7 cm (top-aligned)
- Data Rows: 3.85 cm (response column top-aligned, others center-aligned)

### Confidence Scoring

| Score Range | Level | Meaning |
|-------------|-------|---------|
| 80-100 | High | Strong indication of unauthenticated access |
| 50-79 | Medium | Possible unauthenticated access |
| 20-49 | Low | Unlikely but worth investigating |
| 0-19 | Inconclusive | Protected or error state |

---

## 💡 Examples

### Example 1: Basic Scan

```bash
$ python3 unauth_checker.py -u https://api.example.com/openapi.json

[*] OpenAPI loaded successfully
[*] Base URL: https://api.example.com
[*] Total endpoints detected: 150
[*] Output file: api-example-com.csv
Progress: [████████████████████████] 450 / 450 endpoints evaluated
[*] Scan completed successfully
[*] Results stored in api-example-com.csv
[*] Excel file with formatting: api-example-com.xlsx
```

### Example 2: Verbose Mode

```bash
$ python3 unauth_checker.py -u https://api.example.com/openapi.json -v

[*] OpenAPI loaded successfully
[*] Base URL: https://api.example.com
[*] Total endpoints detected: 150
[*] Output file: api-example-com.csv

[+] Testing endpoint (1/150): GET /api/users
    Detected parameters (2): id, name
    [*] Agent generating sample values...
    [*] 4 sample values created
    [*] Testing 3 cases: empty params + 2 sample sets
    [*] Test case 1/3: Empty parameters
        → Status: 401
        → Response:
        {
          "status": "Error",
          "code": 401,
          "message": "Unauthorized!"
        }
    [*] Test case 2/3: set_1 - {"id": "12345", "name": "John Doe"}
        → Status: 200
        → Response:
        {
          "id": "12345",
          "name": "John Doe",
          "email": "john@example.com"
        }
    [+] Endpoint evaluation completed
    [+] 3 result(s) appended to CSV
```

### Example 3: CSV Output Sample

```csv
endpoint,method,params_count,params_values,status_codes,response,confidence,confidence_level,notes
/api/users,GET,2,{},401,"{""status"": ""Error"", ""code"": 401}",0,Inconclusive,Test case: empty
/api/users,GET,2,"{""id"": ""12345"", ""name"": ""John""}",200,"{""id"": ""12345"", ""name"": ""John""}",60,Medium,Test case: set_1
/api/users,GET,2,"{""id"": ""67890"", ""name"": ""Jane""}",200,"{""id"": ""67890"", ""name"": ""Jane""}",60,Medium,Test case: set_2
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

#### ❌ CSV/Excel file not created

**Solution:**
- Check write permissions in current directory
- Verify disk space
- Check if file path is valid
- For Excel files, ensure `openpyxl` is installed: `pip install openpyxl`

#### ❌ Excel file not updating in real-time

**Solution:**
- Excel files are saved after each row by default
- If Excel file appears locked, close it and let the scan complete
- The file will be properly saved at the end of the scan

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
