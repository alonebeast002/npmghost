# NPM Ghost

A fast dependency confusion recon tool that crawls JavaScript and source map files to extract NPM package names and checks if they exist on the public registry.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![PyPI](https://img.shields.io/badge/PyPI-npmghost-orange?style=flat-square&logo=pypi)

---

## What it does

- Crawls a target URL and extracts all linked `.js` and `.map` files
- Parses `require()` calls and `node_modules/` references to extract package names
- Checks each package against the NPM registry
- Flags packages that do not exist — potential dependency confusion targets
- Handles gzip, deflate, and brotli compressed responses
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

## Installation

```bash
pip install npmghost
```

From source:

```bash
git clone https://github.com/alonebeast002/npmghost.git
cd npmghost
pip install .
```

```bash
npmghost
```

---

## Requirements

- Python 3.8+
- `chardet`
- `brotli` (optional, enables brotli decompression)
- `subfinder` (optional, required for wildcard mode)

---

## Output Files

| File | Content |
|------|---------|
| `all_packages.txt` | All extracted package names |
| `all_urls.txt` | All discovered `.js` and `.map` URLs |
| `all_urls.json` | Same URLs in JSON format |
| `npm_ghost_results.json` | Full scan results with package name, version, status, and source URL |

---

## Disclaimer

For authorized security testing and bug bounty research only. Use on targets you have permission to test.

---

## Author

alonebeast002 — [GitHub](https://github.com/alonebeast002)

## License

[MIT](LICENSE)
