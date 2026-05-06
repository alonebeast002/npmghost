#!/usr/bin/env python3

import sys
import os
import re
import time
import json
import signal
import threading
import ssl
import gzip
import zlib
import urllib.parse
import urllib.request
import urllib.error
import http.client
import socket
import struct
import subprocess
import shutil
import chardet
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import brotli
    BROTLI_OK = True
except ImportError:
    BROTLI_OK = False

W, G, R, Y, C, M, RST, BLD, DIM = (
    "\033[97m", "\033[92m", "\033[91m", "\033[93m",
    "\033[96m", "\033[95m", "\033[0m", "\033[1m", "\033[2m"
)
ORG = "\033[38;5;208m"

_interrupted          = False
total_js_scanned      = 0
total_pkgs_found      = 0
total_200             = 0
total_404             = 0
total_subs_scanned    = 0   # NEW
total_sub_errors      = 0   # NEW
_lock                 = threading.Lock()
_print_lock           = threading.Lock()

def _sigint(sig, frame):
    global _interrupted
    _interrupted = True
    sys.stdout.write("\n")
    sys.stdout.flush()
    os._exit(0)

signal.signal(signal.SIGINT, _sigint)

def strip_ansi(text):
    return re.sub(r'\033\[[0-9;]*m', '', text)

def get_cols():
    try:
        return os.get_terminal_size().columns
    except:
        return 80

def cprint(line):
    cols = get_cols()
    clean = strip_ansi(line)
    pad = " " * max(0, (cols - len(clean)) // 2)
    print(f"{pad}{line}")

def lprint(line):
    cols = get_cols()
    pad = " " * max(0, (cols - 60) // 2)
    print(f"{pad}{line}")

def print_block(lines):
    cols = get_cols()
    max_clean = max((len(strip_ansi(l)) for l in lines), default=0)
    pad = " " * max(0, (cols - max_clean) // 2)
    for line in lines:
        print(f"{pad}{line}")

def print_sep(char="─", width=60):
    cols = get_cols()
    pad = " " * max(0, (cols - width) // 2)
    print(f"{pad}{BLD}{W}{char * width}{RST}")

BANNER_TOP = [
    f"{BLD}{C}███╗   ██╗██████╗ ███╗   ███╗{RST}",
    f"{BLD}{C}████╗  ██║██╔══██╗████╗ ████║{RST}",
    f"{BLD}{C}██╔██╗ ██║██████╔╝██╔████╔██║{RST}",
    f"{BLD}{C}██║╚██╗██║██╔═══╝ ██║╚██╔╝██║{RST}",
    f"{BLD}{C}██║ ╚████║██║     ██║ ╚═╝ ██║{RST}",
    f"{BLD}{C}╚═╝  ╚═══╝╚═╝     ╚═╝     ╚═╝{RST}",
]
BANNER_BOT = [
    f"{BLD}{G} ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗{RST}",
    f"{BLD}{G}██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝{RST}",
    f"{BLD}{G}██║  ███╗███████║██║   ██║███████╗   ██║   {RST}",
    f"{BLD}{G}██║   ██║██╔══██║██║   ██║╚════██║   ██║   {RST}",
    f"{BLD}{G}╚██████╔╝██║  ██║╚██████╔╝███████║   ██║   {RST}",
    f"{BLD}{G} ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝  {RST}",
]

def print_banner(animate=False):
    all_lines = BANNER_TOP + [""] + BANNER_BOT
    cols = get_cols()
    max_len = max((len(strip_ansi(l)) for l in all_lines if l), default=40)
    pad = " " * max(0, (cols - max_len) // 2)
    print()
    for line in all_lines:
        if line == "":
            print()
        else:
            print(f"{pad}{line}")
            if animate:
                time.sleep(0.022)

def print_header():
    line1 = "v2.2  ·  JS/Map NPM Package Recon  ·  alone_beast_02"
    line2 = "Subfinder · Full-Fetch · Chunked · Ghost Hunting"
    w = max(len(line1), len(line2))
    cols = get_cols()
    pad = " " * max(0, (cols - w) // 2)
    print()
    print(f"{pad}{C}{'═' * w}{RST}")
    print(f"{pad}{BLD}{W}{line1}{RST}")
    print(f"{pad}{DIM}{Y}{line2}{RST}")
    print(f"{pad}{C}{'─' * w}{RST}")
    print()

class Spinner:
    chars = ["⣾","⣽","⣻","⢿","⡿","⣟","⣯","⣷"]
    messages = [
        "NPM Ghost is hunting 👻",
        "Crawling JS — full-page mode...",
        "Extracting require() calls...",
        "Checking npm registry...",
        "Looking for ghost packages...",
        "Hunting dependency confusion...",
        "Private package ahead? 👀",
        "Querying registry.npmjs.org...",
        "Reading compressed responses...",
        "Chunked transfer — reassembling...",
        "Brotli / gzip decoded...",
        "Source maps — deep scan...",
    ]

    def __init__(self, extra_msg=""):
        self.running   = False
        self.idx       = 0
        self.msg_idx   = 0
        self.extra_msg = extra_msg

    def set_msg(self, msg):
        self.extra_msg = msg

    def _render(self):
        msg = self.extra_msg if self.extra_msg else self.messages[self.msg_idx % len(self.messages)]
        ch  = self.chars[self.idx % 8]
        cols = get_cols()
        # CHANGED: added subs= and err= counters at the end
        stats = (
            f"{ORG}{ch}{RST} {DIM}{msg}{RST}  "
            f"{DIM}js={RST}{C}{total_js_scanned}{RST} "
            f"{DIM}pkg={RST}{M}{total_pkgs_found}{RST} "
            f"{G}✓{total_200}{RST} "
            f"{R}✗{total_404}{RST} "
            f"{DIM}subs={RST}{C}{total_subs_scanned}{RST} "
            f"{DIM}err={RST}{R}{total_sub_errors}{RST}"
        )
        clean_len = len(strip_ansi(stats))
        pad = " " * max(0, (cols - clean_len) // 2)
        sys.stdout.write(f"\r\033[2K{pad}{stats}")
        sys.stdout.flush()

    def spin(self):
        while self.running:
            self._render()
            self.idx += 1
            if self.idx % 30 == 0 and not self.extra_msg:
                self.msg_idx += 1
            time.sleep(0.1)

    def start(self):
        self.running = True
        sys.stdout.write("\n")
        sys.stdout.flush()
        threading.Thread(target=self.spin, daemon=True).start()

    def stop(self):
        self.running = False
        time.sleep(0.2)
        sys.stdout.write("\r\033[2K")
        sys.stdout.flush()
        print()

def show_coffee(mode_label=""):
    os.system("clear")
    print_banner()
    cols = get_cols()

    text1 = "[tea]  engines loaded · ghost hunt active"
    text2 = f"mode : {mode_label}"
    inner = max(len(text1), len(text2)) + 4
    pad   = " " * max(0, (cols - inner - 2) // 2)

    def brow(text, color=""):
        fill = inner - 2 - len(text)
        return f"{pad}{ORG}│{RST} {color}{text}{RST}{' ' * max(0, fill)} {ORG}│{RST}"

    print(f"{pad}{ORG}┌{'─' * inner}┐{RST}")
    print(brow(text1, Y))
    print(brow(text2, C))
    print(f"{pad}{ORG}└{'─' * inner}┘{RST}")
    print()

    art = [
        f"{Y}   ( (   {RST}  {W}Grab a coffee and relax...{RST}",
        f"{Y}    ) )  {RST}  {G}Full-page fetch engine loaded...{RST}",
        f"{Y}  ......{RST}   {C}Compression handlers ready...{RST}",
        f"{C}  |    | {RST}  {Y}Ghost hunt begins!{RST}",
        f"{C}   \  / {RST}",
        f"{G}    `--'{RST}",
    ]
    max_len = max(len(strip_ansi(l)) for l in art)
    art_pad = " " * max(0, (cols - max_len) // 2)
    for line in art:
        print(f"{art_pad}{line}")
        time.sleep(0.14)
    time.sleep(0.6)
    print()
    cprint(f"{G}[+]{RST} {W}NPM Ghost v2.2 — scan engine active...{RST}")
    print()
    time.sleep(0.3)

PKG_RE = re.compile(
    r'''require\(\s*['"`](@?[a-zA-Z0-9][\w\-\.]*(?:/[\w\-\.]+)?)\s*['"`]\s*\)'''
)

NODE_MODULES_RE = re.compile(
    r'''node_modules/([a-zA-Z0-9][a-zA-Z0-9\-\._]*)(?:/|['"`\s])'''
)

NODE_BUILTINS = {
    "assert","buffer","child_process","cluster","console","constants","crypto",
    "dgram","dns","domain","events","fs","http","https","module","net","os",
    "path","perf_hooks","process","punycode","querystring","readline","repl",
    "stream","string_decoder","sys","timers","tls","tty","url","util","v8","vm",
    "worker_threads","zlib","_http_agent","_http_client","_stream_duplex",
    "_stream_passthrough","_stream_readable","_stream_transform","_stream_writable",
}

def _root_pkg(name):
    if name.startswith("@"):
        return None
    return name.split("/")[0]

def extract_packages(content):
    pkgs = set()

    for m in PKG_RE.finditer(content):
        raw = m.group(1)
        if raw.startswith(".") or raw.startswith("/"):
            continue
        root = _root_pkg(raw)
        if root is None:
            continue
        if root in NODE_BUILTINS:
            continue
        pkgs.add(root)

    for m in NODE_MODULES_RE.finditer(content):
        name = m.group(1)
        if name in NODE_BUILTINS:
            continue
        pkgs.add(name)

    return pkgs

NPM_API = "https://registry.npmjs.org/"

def check_npm(pkg_name):
    encoded = urllib.parse.quote(pkg_name, safe="@/")
    url = NPM_API + encoded
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "npmghost-recon/2.2"})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                latest = data.get("dist-tags", {}).get("latest", "?")
                return 200, True, latest
            return resp.status, False, None
    except urllib.error.HTTPError as e:
        return e.code, False, None
    except:
        return 0, False, None

def _decode_body(raw_bytes, encoding_header):
    enc = (encoding_header or "").strip().lower()
    try:
        if enc == "br" and BROTLI_OK:
            return brotli.decompress(raw_bytes).decode("utf-8", errors="replace")
        if enc == "gzip":
            return gzip.decompress(raw_bytes).decode("utf-8", errors="replace")
        if enc in ("deflate", "zlib"):
            try:
                return zlib.decompress(raw_bytes).decode("utf-8", errors="replace")
            except zlib.error:
                return zlib.decompress(raw_bytes, -zlib.MAX_WBITS).decode("utf-8", errors="replace")
    except Exception:
        pass
    detected = chardet.detect(raw_bytes[:4096])
    enc_guess = detected.get("encoding") or "utf-8"
    return raw_bytes.decode(enc_guess, errors="replace")

def _read_chunked(sock_file):
    body = BytesIO()
    while True:
        line = sock_file.readline().decode("ascii", errors="replace").strip()
        if not line:
            continue
        try:
            chunk_size = int(line.split(";")[0], 16)
        except ValueError:
            break
        if chunk_size == 0:
            break
        data = b""
        while len(data) < chunk_size:
            packet = sock_file.read(chunk_size - len(data))
            if not packet:
                break
            data += packet
        body.write(data)
        sock_file.readline()
    return body.getvalue()

def fetch_full(url, max_size=20 * 1024 * 1024, timeout=20, retries=3):
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    host   = parsed.netloc
    path   = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    hdrs = {
        "Host": host,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close",
    }

    for attempt in range(retries):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            hostname = host.split(":")[0]
            if ":" in host:
                port = int(host.split(":")[1])
            else:
                port = 443 if scheme == "https" else 80

            raw_sock = socket.create_connection((hostname, port), timeout=timeout)
            sock = ctx.wrap_socket(raw_sock, server_hostname=hostname) if scheme == "https" else raw_sock

            req_str = f"GET {path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hdrs.items()) + "\r\n"
            sock.sendall(req_str.encode("utf-8"))

            sock_file = sock.makefile("rb")
            status_line = sock_file.readline().decode("ascii", errors="replace").strip()
            parts = status_line.split(" ", 2)
            status_code = int(parts[1]) if len(parts) >= 2 else 0

            resp_headers = {}
            while True:
                hline = sock_file.readline().decode("ascii", errors="replace").strip()
                if not hline:
                    break
                if ":" in hline:
                    k, v = hline.split(":", 1)
                    resp_headers[k.strip().lower()] = v.strip()

            if status_code in (301, 302, 303, 307, 308):
                location = resp_headers.get("location", "")
                sock.close()
                if location and retries > 1:
                    return fetch_full(urllib.parse.urljoin(url, location), max_size, timeout, retries - 1)
                return status_code, ""

            transfer_enc  = resp_headers.get("transfer-encoding", "").lower()
            content_enc   = resp_headers.get("content-encoding", "")
            content_len   = resp_headers.get("content-length", None)

            if "chunked" in transfer_enc:
                raw_bytes = _read_chunked(sock_file)
            elif content_len is not None:
                try:
                    to_read = int(content_len)
                except ValueError:
                    to_read = max_size
                raw_bytes = b""
                while len(raw_bytes) < to_read:
                    chunk = sock_file.read(min(65536, to_read - len(raw_bytes)))
                    if not chunk:
                        break
                    raw_bytes += chunk
                    if len(raw_bytes) >= max_size:
                        break
            else:
                raw_bytes = b""
                while True:
                    chunk = sock_file.read(65536)
                    if not chunk:
                        break
                    raw_bytes += chunk
                    if len(raw_bytes) >= max_size:
                        break

            sock.close()
            return status_code, _decode_body(raw_bytes, content_enc)

        except (socket.timeout, ConnectionResetError, ssl.SSLError):
            if attempt == retries - 1:
                return 0, ""
            time.sleep(0.5 * (attempt + 1))
        except Exception:
            return 0, ""

    return 0, ""

def fetch_sourcemap_sources(map_content, base_url):
    collected = ""
    try:
        data = json.loads(map_content)
        for sc in data.get("sourcesContent", []):
            if sc:
                collected += sc + "\n"
        for src in data.get("sources", []):
            if src and not src.startswith("webpack") and not src.startswith("node_modules"):
                full = urllib.parse.urljoin(base_url, src)
                st, sc = fetch_full(full)
                if st == 200:
                    collected += sc + "\n"
    except Exception:
        pass
    return collected

def save_result(data):
    entry = {
        "package"        : data.get("package", ""),
        "package_version": data.get("latest", ""),
        "npm_status"     : data.get("npm_status", 0),
        "public"         : data.get("public", False),
        "source_js_url"  : data.get("source_file", ""),
        "time"           : data.get("time", ""),
    }
    with open("npm_ghost_results.json", "a") as f:
        f.write(json.dumps(entry, indent=4) + "\n\n")

def save_all_pkgs(pkgs_set):
    with open("all_packages.txt", "a") as f:
        for p in sorted(pkgs_set):
            f.write(p + "\n")

def save_url(url):
    if not (url.endswith(".js") or url.endswith(".map")):
        return
    entry = json.dumps({"url": url}, indent=4)
    with open("all_urls.json", "a") as f:
        f.write(entry + "\n\n")
    with open("all_urls.txt", "a") as f:
        f.write(url + "\n")

def print_pkg_result(pkg, status, latest, source):
    global total_200, total_404
    if status == 200:
        badge = f"{BLD}{G}[ 200  PUBLIC ]{RST}"
        ver   = f" {DIM}v{latest}{RST}" if latest and latest != "?" else ""
        line  = f"  {badge} {W}{pkg}{RST}{ver}"
        with _lock:
            total_200 += 1
    elif status == 404:
        badge = f"{BLD}{R}[ 404  GHOST  ]{RST}"
        line  = f"  {badge} {Y}{BLD}{pkg}{RST}  {R}◄ NOT on npm!{RST}"
        with _lock:
            total_404 += 1
    else:
        badge = f"{BLD}{DIM}[ ???  UNKNWN ]{RST}"
        line  = f"  {badge} {DIM}{pkg}{RST}"

    with _print_lock:
        sys.stdout.write("\r\033[2K")
        print(line)

def process_content(url, content, spinner=None):
    global total_js_scanned, total_pkgs_found
    with _lock:
        total_js_scanned += 1
    save_url(url)
    pkgs = extract_packages(content)
    if not pkgs:
        return set()
    with _lock:
        total_pkgs_found += len(pkgs)
    save_all_pkgs(pkgs)
    results = []
    with ThreadPoolExecutor(max_workers=15) as ex:
        futs = {ex.submit(check_npm, p): p for p in pkgs}
        for fut in as_completed(futs):
            if _interrupted:
                break
            pkg = futs[fut]
            try:
                status, is_pub, latest = fut.result()
            except:
                status, is_pub, latest = 0, False, None
            print_pkg_result(pkg, status, latest, url)
            save_result({
                "package": pkg,
                "npm_status": status,
                "public": is_pub,
                "latest": latest,
                "source_file": url,
                "time": time.ctime()
            })
            results.append((pkg, status))
    return set(p for p, s in results if s == 404)

def extract_js_links(text, base_url):
    found = set()
    pats = [
        r'src\s*=\s*[\'"]([^\'"]+\.js)[\'"]',
        r'href\s*=\s*[\'"]([^\'"]+\.js)[\'"]',
        r'[\'"`](/[^\'"`\s]+\.js)[\'"`]',
        r'import\s*\([\'"]([^\'"]+\.js)[\'"]',
        r'loadScript\s*\([\'"]([^\'"]+\.js)[\'"]',
    ]
    for p in pats:
        for m in re.finditer(p, text):
            full = urllib.parse.urljoin(base_url, m.group(1)).split("?")[0]
            if full.endswith(".js"):
                found.add(full)
    return found

def crawl_target(target, spinner=None):
    global total_subs_scanned, total_sub_errors
    if not target.startswith("http"):
        target = "https://" + target
    scanned, queue = set(), {target}
    ghost_pkgs = set()
    had_success = False
    for _ in range(2):
        if not queue or _interrupted:
            break
        batch = list(queue - scanned)
        scanned.update(batch)
        queue = set()
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs = {ex.submit(fetch_full, u): u for u in batch}
            for fut in as_completed(futs):
                if _interrupted:
                    break
                url = futs[fut]
                status, content = fut.result()
                if status != 200 or not content:
                    with _lock:
                        total_sub_errors += 1
                    continue
                had_success = True
                ghosts = process_content(url, content, spinner)
                ghost_pkgs.update(ghosts)
                if not url.endswith(".js"):
                    for js in extract_js_links(content, url):
                        if js not in scanned:
                            queue.add(js)
                if url.endswith(".js"):
                    map_url = url + ".map"
                    ms, mc = fetch_full(map_url)
                    if ms == 200 and mc:
                        g2 = process_content(map_url, mc, spinner)
                        ghost_pkgs.update(g2)
                        extra = fetch_sourcemap_sources(mc, map_url)
                        if extra:
                            g3 = process_content(map_url + "[sources]", extra, spinner)
                            ghost_pkgs.update(g3)
    with _lock:
        total_subs_scanned += 1
    return ghost_pkgs

def scan_file_list(filepath):
    if not os.path.exists(filepath):
        cprint(f"\n{R}[✗] File not found: {filepath}{RST}\n")
        return set()
    with open(filepath) as f:
        urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    cprint(f"\n{G}[✓]{RST} {W}{len(urls)} JS/.map URLs loaded{RST}\n")
    time.sleep(0.3)
    show_coffee("JS/Map list mode")
    ghost_pkgs = set()
    spinner = Spinner()
    spinner.start()
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(fetch_full, u): u for u in urls}
        for fut in as_completed(futs):
            if _interrupted:
                break
            url = futs[fut]
            status, content = fut.result()
            if status == 200 and content:
                g = process_content(url, content, spinner)
                ghost_pkgs.update(g)
    spinner.stop()
    return ghost_pkgs

def _run_silent(cmd):
    return subprocess.run(
        cmd, shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ).returncode

def _spinner_status(spinner, msg):
    with _print_lock:
        sys.stdout.write(f"\r\033[2K")
        cols = get_cols()
        pad = " " * max(0, (cols - len(strip_ansi(msg))) // 2)
        sys.stdout.write(f"{pad}{msg}\n")
        sys.stdout.flush()

def ensure_go(spinner):
    go_bin = shutil.which("go")
    if go_bin:
        return go_bin

    _spinner_status(spinner, f"{Y}[~] go not found — installing golang...{RST}")

    pkg_mgr = None
    if shutil.which("apt-get"):
        pkg_mgr = "apt-get install -y golang-go"
    elif shutil.which("apt"):
        pkg_mgr = "apt install -y golang-go"
    elif shutil.which("pkg"):
        pkg_mgr = "pkg install -y golang"
    elif shutil.which("yum"):
        pkg_mgr = "yum install -y golang"
    elif shutil.which("dnf"):
        pkg_mgr = "dnf install -y golang"
    elif shutil.which("pacman"):
        pkg_mgr = "pacman -S --noconfirm go"
    elif shutil.which("brew"):
        pkg_mgr = "brew install go"

    if not pkg_mgr:
        _spinner_status(spinner, f"{R}[✗] No package manager found — install golang manually{RST}")
        return None

    ret = _run_silent(pkg_mgr)
    if ret != 0:
        _spinner_status(spinner, f"{R}[✗] golang install failed — install manually{RST}")
        return None

    go_bin = shutil.which("go") or "/usr/local/go/bin/go"
    if not os.path.isfile(go_bin or ""):
        _spinner_status(spinner, f"{R}[✗] go binary not found after install{RST}")
        return None

    _spinner_status(spinner, f"{G}[✓] golang installed{RST}")
    return go_bin

def ensure_subfinder(spinner):
    subfinder_path = os.path.expanduser("~/go/bin/subfinder")

    if os.path.isfile(subfinder_path):
        _spinner_status(spinner, f"{G}[✓] subfinder found{RST}")
        return subfinder_path

    _spinner_status(spinner, f"{Y}[~] subfinder not found — installing...{RST}")

    go_bin = ensure_go(spinner)
    if not go_bin:
        return None

    env = os.environ.copy()
    env["GOPATH"] = os.path.expanduser("~/go")

    _spinner_status(spinner, f"{Y}[~] Installing subfinder via go install...{RST}")
    ret = subprocess.run(
        "go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
        shell=True, env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ).returncode

    if ret != 0 or not os.path.isfile(subfinder_path):
        _spinner_status(spinner, f"{R}[✗] subfinder install failed{RST}")
        return None

    _spinner_status(spinner, f"{G}[✓] subfinder installed{RST}")
    time.sleep(0.3)
    return subfinder_path

def run_subfinder(domain, spinner):
    subfinder_path = ensure_subfinder(spinner)
    if not subfinder_path:
        return []

    spinner.set_msg(f"subfinder — enumerating {domain}...")
    try:
        result = subprocess.run(
            [subfinder_path, "-d", domain, "-silent"],
            capture_output=True, text=True, timeout=120
        )
        subs = [s.strip() for s in result.stdout.splitlines() if s.strip()]
        spinner.set_msg("")
        return subs
    except subprocess.TimeoutExpired:
        spinner.set_msg("")
        return []
    except Exception:
        spinner.set_msg("")
        return []

def wildcard_scan(domain):
    show_coffee("Wildcard · subfinder mode")
    spinner = Spinner()
    spinner.start()

    cols = get_cols()

    with _print_lock:
        sys.stdout.write(f"\r\033[2K")
        msg = f"{C}[~]{RST} Running subfinder on {BLD}{domain}{RST}..."
        pad = " " * max(0, (cols - len(strip_ansi(msg))) // 2)
        sys.stdout.write(f"{pad}{msg}\n")
        sys.stdout.flush()

    subdomains = run_subfinder(domain, spinner)

    if not subdomains:
        with _print_lock:
            sys.stdout.write(f"\r\033[2K")
            msg = f"{R}[✗] No subdomains found for {domain}{RST}"
            pad = " " * max(0, (cols - len(strip_ansi(msg))) // 2)
            sys.stdout.write(f"{pad}{msg}\n")
            sys.stdout.flush()
        spinner.stop()
        return set()

    with _print_lock:
        sys.stdout.write(f"\r\033[2K")
        msg = f"{G}[✓]{RST} {BLD}{len(subdomains)}{RST} subdomains found — scanning all..."
        pad = " " * max(0, (cols - len(strip_ansi(msg))) // 2)
        sys.stdout.write(f"{pad}{msg}\n")
        sys.stdout.flush()

    time.sleep(0.3)
    spinner.set_msg("")

    ghost_pkgs = set()
    for sub in subdomains:
        if _interrupted:
            break
        g = crawl_target(sub, spinner)
        ghost_pkgs.update(g)

    spinner.stop()
    return ghost_pkgs

def show_intro():
    os.system("clear")
    print_banner(animate=True)
    cols = get_cols()

    menu_items = [
        ("1", f"{ORG}", "Wildcard Domain", "subfinder + enumerate + crawl"),
        ("2", f"{G}",   "Single URL",      "direct crawl + JS/map scan"),
        ("3", f"{Y}",   "Subdomain List",  ".txt multi-target batch"),
        ("4", f"{C}",   "JS / .map List",  "direct file scan"),
    ]

    label_w = max(len(x[2]) for x in menu_items)
    desc_w  = max(len(x[3]) for x in menu_items)
    inner_w = 2 + 1 + 1 + 2 + label_w + 2 + desc_w + 2
    pad     = " " * max(0, (cols - inner_w - 2) // 2)

    title    = " SELECT MODE "
    tl       = len(title)
    left_bar = (inner_w - tl) // 2
    rbar     = inner_w - tl - left_bar

    print(f"{pad}{ORG}┌{'─' * left_bar}{BLD}{W}{title}{RST}{ORG}{'─' * rbar}┐{RST}")
    print(f"{pad}{ORG}│{RST}{' ' * inner_w}{ORG}│{RST}")

    for num, col, label, desc in menu_items:
        visible = f"  {num}  {label:<{label_w}}  {desc}  "
        colored = f"  {col}{BLD}{num}{RST}  {BLD}{W}{label:<{label_w}}{RST}  {DIM}{desc}{RST}  "
        rpad = inner_w - len(visible)
        print(f"{pad}{ORG}│{RST}{colored}{' ' * max(0, rpad)}{ORG}│{RST}")

    print(f"{pad}{ORG}│{RST}{' ' * inner_w}{ORG}│{RST}")
    print(f"{pad}{ORG}└{'─' * inner_w}┘{RST}")
    print()

def show_results(ghost_pkgs):
    os.system("clear")
    print_banner()
    cols = get_cols()
    pad = " " * max(0, (cols - 46) // 2)

    print(f"{pad}{ORG}┌──────────────────────────────────────────────┐{RST}")
    print(f"{pad}{ORG}│{RST}  {BLD}{W}HUNT COMPLETE{RST}                                {ORG}│{RST}")
    print(f"{pad}{ORG}├──────────────────────────────────────────────┤{RST}")

    stats = [
        (f"{C}js files scanned  {RST}", f"{BLD}{C}{total_js_scanned}{RST}"),
        (f"{M}packages found    {RST}", f"{BLD}{M}{total_pkgs_found}{RST}"),
        (f"{G}public  (200)     {RST}", f"{BLD}{G}{total_200}{RST}"),
        (f"{R}ghost   (404)     {RST}", f"{BLD}{R}{total_404}{RST}"),
        (f"{C}subdomains scanned{RST}", f"{BLD}{C}{total_subs_scanned}{RST}"),
        (f"{R}subdomain errors  {RST}", f"{BLD}{R}{total_sub_errors}{RST}"),
    ]
    for label, val in stats:
        row = f"  {label}  {val}"
        clean = len(strip_ansi(row))
        print(f"{pad}{ORG}│{RST}{row}{' ' * max(0, 46 - clean)}{ORG}│{RST}")

    print(f"{pad}{ORG}└──────────────────────────────────────────────┘{RST}")
    print()

    if ghost_pkgs:
        print(f"{pad}{R}{BLD}  ⚠  GHOST PACKAGES — NOT ON npm:{RST}")
        print()
        for pkg in sorted(ghost_pkgs):
            cprint(f"  {R}›{RST} {Y}{BLD}{pkg}{RST}")
        print()

    print(f"{pad}{DIM}  output → all_packages.txt  ·  npm_ghost_results.json{RST}")
    print()

    if total_404 > 0:
        cprint(f"{R}{BLD}  ⚠  dependency confusion possible — report responsibly{RST}")
    else:
        cprint(f"{G}  ✓  all packages live on npm{RST}")
    print()

def main():
    show_intro()
    cols = get_cols()
    pad = " " * max(0, (cols - 32) // 2)
    choice = input(f"{pad}{G}>{RST} {BLD}{G}Mode [{W}1/2/3/4{G}]{RST}{G}: {RST}").strip()
    ghost_pkgs = set()

    if choice == "1":
        dpad = " " * max(0, (cols - 30) // 2)
        domain = input(f"{dpad}{W}Enter wildcard domain {DIM}(e.g. example.com){RST}: ").strip()
        domain = domain.lstrip("*.")
        if not domain:
            cprint(f"\n{R}[✗] No domain entered{RST}\n")
            return
        ghost_pkgs = wildcard_scan(domain)

    elif choice == "2":
        upad = " " * max(0, (cols - 22) // 2)
        target = input(f"{upad}{W}Enter URL: {RST}").strip()
        print()
        cprint(f"{G}[✓]{RST} {W}Target set — starting full-page crawl...{RST}")
        time.sleep(0.3)
        show_coffee("Single URL mode")
        spinner = Spinner()
        spinner.start()
        ghost_pkgs = crawl_target(target, spinner)
        spinner.stop()

    elif choice == "3":
        fpad = " " * max(0, (cols - 30) // 2)
        path = input(f"{fpad}{W}Enter subdomain list path: {RST}").strip()
        if not os.path.exists(path):
            cprint(f"\n{R}[✗] File not found!{RST}\n")
            return
        with open(path) as f:
            targets = [l.strip() for l in f if l.strip()]
        cprint(f"\n{G}[✓]{RST} {W}{len(targets)} targets loaded{RST}")
        time.sleep(0.3)
        show_coffee("Subdomain list mode")
        spinner = Spinner()
        spinner.start()
        for t in targets:
            if _interrupted:
                break
            g = crawl_target(t, spinner)
            ghost_pkgs.update(g)
        spinner.stop()

    elif choice == "4":
        jpad = " " * max(0, (cols - 30) // 2)
        path = input(f"{jpad}{W}Enter JS/.map list path: {RST}").strip()
        ghost_pkgs = scan_file_list(path)

    else:
        cprint(f"\n{R}[✗] Invalid choice — enter 1, 2, 3, or 4{RST}\n")
        return

    show_results(ghost_pkgs)

if __name__ == "__main__":
    main()
