# NPM Ghost

A fast, dependency confusion recon tool that crawls JavaScript and source map files to extract NPM package names and checks if they exist on the public registry.

---

## What it does

- Crawls a target URL and extracts all linked `.js` and `.map` files
- Parses `require()` calls and `node_modules/` references to extract package names
- Checks each package against the NPM registry
- Flags packages that do not exist — potential dependency confusion targets
- Handles gzip, deflate, and brotli compressed responses
- Follows chunked transfer encoding
- Saves results to structured JSON and plain text output files

---

## Modes

| Mode | Description |
|------|-------------|
| Wildcard Domain | Runs subfinder to enumerate subdomains, then crawls all of them |
| Single URL | Direct crawl of a single target URL |
| Subdomain List | Batch scan from a `.txt` file of subdomains |
| JS / Map List | Direct scan of a `.txt` file of JS or map file URLs |

---

## Output Files

| File | Content |
|------|---------|
| `all_packages.txt` | All extracted package names, one per line |
| `all_urls.txt` | All discovered `.js` and `.map` URLs, one per line |
| `all_urls.json` | Same URLs in structured JSON format |
| `npm_ghost_results.json` | Full scan results with package name, version, status, and source URL |

---

## Installation

```bash
pip install npm-ghost
```

Or from source:

```bash
https://github.com/alonebeast002/npmghost.git
cd npmghost
pip install -r requirements.txt
python setup.py install
```
**Run**
```
npmghost
```
---

## Requirements

- Python 3.8+
- `chardet`
- `brotli` (optional, enables brotli decompression)
- `subfinder` (optional, required for wildcard mode — installed automatically if Go is available)

---

## Use Case

Dependency confusion is a supply chain attack where a public package with the same name as a private internal package gets installed instead. This tool helps security researchers identify internal package names exposed in client-side JavaScript that do not exist on the public NPM registry.

**Use only on targets you have permission to test.**

---

## Author

alonebeast002
