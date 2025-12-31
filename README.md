# 🔓 Unauth-Checker

<div align="center">

**AI-Powered Unauthenticated API Endpoint Discovery Tool**

[![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Mistral AI](https://img.shields.io/badge/Powered%20by-Mistral%20AI-orange.svg)](https://mistral.ai/)

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
- [License](#-license)

---

## 🎯 Overview

**Unauth-Checker** is an intelligent security testing tool that automatically identifies unauthenticated API endpoints by:

- 📥 Parsing OpenAPI/Swagger specifications
- 🤖 Using **Mistral AI** to generate realistic parameter values
- 🧪 Testing endpoints with multiple parameter combinations
- 📊 Generating detailed CSV reports with response analysis

Perfect for security researchers, penetration testers, and developers who need to audit API security.

---

## ✨ Features

### 🚀 Core Capabilities

- ✅ **OpenAPI 2.0 & 3.0+ Support** - Works with both Swagger and OpenAPI specifications
- ✅ **AI-Powered Parameter Generation** - Uses Mistral AI to create realistic test values
- ✅ **Triple Testing Strategy** - Tests each endpoint with:
  - Empty parameters
  - First AI-generated parameter set
  - Second AI-generated parameter set
- ✅ **Resume Capability** - Automatically resumes interrupted scans
- ✅ **Smart File Versioning** - Auto-generates versioned output files (e.g., `api.example.com.csv`, `api.example.com1.csv`)
- ✅ **Progress Tracking** - Real-time progress bar with detailed statistics
- ✅ **Comprehensive CSV Reports** - Includes:
  - Endpoint paths and HTTP methods
  - Parameter counts and values used
  - HTTP status codes received
  - Full response bodies
  - Confidence scores
  - Detailed notes

### 🎨 Additional Features

- 🔄 **Incremental CSV Writing** - Results saved in real-time
- 📈 **Confidence Scoring** - Automatic risk assessment
- 🎯 **Verbose Mode** - Detailed execution logs for debugging
- 🌐 **URL & File Input** - Support for remote URLs and local files
- ⚡ **Error Handling** - Graceful failure recovery

---

## 📦 Prerequisites

Before installing Unauth-Checker, ensure you have:

- **Python 3.6+** installed on your system
- **Mistral AI API Key** ([Get one here](https://console.mistral.ai/))
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
pip install requests
```

Or using `pip3`:

```bash
pip3 install requests
```

### Step 3: Set Up Mistral AI API Key

**Option A: Environment Variable (Recommended)**

```bash
# Linux/macOS
export MISTRAL_API_KEY="your-mistral-api-key-here"

# Windows (PowerShell)
$env:MISTRAL_API_KEY="your-mistral-api-key-here"

# Windows (CMD)
set MISTRAL_API_KEY=your-mistral-api-key-here
```

**Option B: Add to `.bashrc` or `.zshrc` (Linux/macOS)**

```bash
echo 'export MISTRAL_API_KEY="your-mistral-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

**Option C: Create `.env` file (if using python-dotenv)**

```bash
echo "MISTRAL_API_KEY=your-mistral-api-key-here" > .env
```

### Step 4: Verify Installation

```bash
python3 unauth_checker.py --help
```

You should see the help menu. If you get an error about missing `MISTRAL_API_KEY`, make sure you've set the environment variable correctly.

---

## ⚙️ Configuration

### Mistral AI Setup

1. **Get Your API Key:**
   - Visit [Mistral AI Console](https://console.mistral.ai/)
   - Sign up or log in
   - Navigate to API Keys section
   - Create a new API key

2. **Model Used:**
   - Default: `mistral-small-latest`
   - Can be modified in `ai_agent.py` if needed

3. **API Endpoint:**
   - Default: `https://api.mistral.ai/v1/chat/completions`
   - No configuration needed unless using custom endpoint

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MISTRAL_API_KEY` | ✅ Yes | Your Mistral AI API key |

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
│  For Each       │─────▶│  Mistral AI  │
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
   - For each parameter, sends request to Mistral AI with:
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
   - Creates CSV file with hostname-based naming
   - Auto-versions files if they already exist
   - Incrementally writes results (resumable)

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

- **Auto-generated:** `{hostname}.csv`
  - Example: `api-example-com.csv`
- **Versioned:** If file exists, creates `{hostname}1.csv`, `{hostname}2.csv`, etc.
- **Custom:** Use `-o` flag to specify custom filename

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

#### ❌ `MISTRAL_API_KEY environment variable not set`

**Solution:**
```bash
export MISTRAL_API_KEY="your-api-key-here"
```

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
- Check Mistral AI service status
- Tool will fallback to "test" values if AI fails

#### ❌ CSV file not created

**Solution:**
- Check write permissions in current directory
- Verify disk space
- Check if file path is valid

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

## 🙏 Acknowledgments

- **Mistral AI** for providing the AI API for parameter generation
- OpenAPI/Swagger community for the specification standards
- All contributors and users of this tool

---

## 📞 Support

For issues, questions, or suggestions:

- 🐛 **Bug Reports:** Open an issue on GitHub
- 💬 **Questions:** Check existing issues or open a new one
- ⭐ **Show Support:** Star the repository if you find it useful!
- 🤝 **LinkedIN:** https://www.linkedin.com/in/yash-prajapati-791m18104/

---

<div align="center">

**Made with ❤️ for the security community**

⭐ **Star this repo if you find it helpful!** ⭐

</div>
