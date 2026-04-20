# 📦 APKeep Dashboard

A cross-platform, browser-based dashboard for bulk downloading APK files from Google Play Store (via APKPure), F-Droid, and Huawei AppGallery — powered by [apkeep](https://github.com/EFForg/apkeep) by EFF.

No credentials required for APKPure downloads. No pip packages required.

---
<img width="690" height="388" alt="image" src="https://github.com/user-attachments/assets/78f89f3d-a4ea-4958-9f2d-ac5db47e0ee9" />

## 📁 Project Files

```
apkeep-dashboard/
├── apkeep_dashboard.py   ← Main application
├── docker-compose.yml    ← Docker Compose config (one command launch)
├── Dockerfile            ← Container build instructions
├── packages.txt          ← Pre-built list of 148 packages across 14 developers
├── requirements.txt      ← Dependency info
└── README.md             ← This file
```

---

## ⚡ Requirements

### Python

| Requirement | Version | Notes |
|---|---|---|
| Python | **3.6+** | Standard library only — no pip installs needed |

> Check your version: `python3 --version`

### apkeep (external binary)

`apkeep` is the underlying download engine. It must be installed separately — it is **not** a Python package. See the [Installation](#️-installation) section below.

### Python packages (optional)

The core dashboard needs **zero pip packages**. However if you want to use the developer page scraper feature:

```
requests>=2.28.0
beautifulsoup4>=4.11.0
```

Install with:
```bash
pip install requests beautifulsoup4
```

> All details are in `requirements.txt`.

---

## 🛠️ Installation

### Step 1 — Install Python

**Linux (Debian / Ubuntu / Kali):**
```bash
sudo apt update && sudo apt install python3 python3-pip -y
python3 --version
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/). During install, check ✅ **"Add Python to PATH"**.
```cmd
python --version
```

**macOS:**
```bash
brew install python3
python3 --version
```

---

### Step 2 — Install apkeep

Pick whichever option suits your system:

#### Option A — Pre-built Binary (Easiest — no Rust needed)

Download from the [releases page](https://github.com/EFForg/apkeep/releases):

| OS | File to download |
|---|---|
| Linux x86_64 | `apkeep-x86_64-unknown-linux-gnu` |
| Windows x86_64 | `apkeep-x86_64-pc-windows-msvc.exe` |
| macOS Intel | `apkeep-x86_64-apple-darwin` |
| macOS Apple Silicon | `apkeep-aarch64-apple-darwin` |

**Linux / macOS:**
```bash
# Download (replace filename with your OS version)
wget https://github.com/EFForg/apkeep/releases/latest/download/apkeep-x86_64-unknown-linux-gnu

# Make executable and move to PATH
chmod +x apkeep-x86_64-unknown-linux-gnu
sudo mv apkeep-x86_64-unknown-linux-gnu /usr/local/bin/apkeep

# Verify
apkeep --version
```

**Windows:**
```cmd
:: Download apkeep-x86_64-pc-windows-msvc.exe from the releases page
:: Rename it to apkeep.exe
:: Move it to C:\Windows\System32\ or any folder in your PATH

apkeep --version
```

---

#### Option B — Via Cargo (Rust package manager)

First install Rust if you don't have it:

**Linux / macOS:**
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

**Windows:**
Download and run [rustup-init.exe](https://rustup.rs)

Then install apkeep:
```bash
cargo install apkeep
apkeep --version
```

---

#### Option C — Termux (Android)
```bash
pkg update && pkg install apkeep
```

---

### Step 3 — Get the Dashboard Files

**Option A — Git clone:**
```bash
git clone https://github.com/binaryguardia/Automations.git
cd Automations/Apkeep
```

**Option B — Manual download:**

Place these files in the same folder:
- `apkeep_dashboard.py`
- `packages.txt`
- `requirements.txt`

---

### Step 4 — Install Optional Python Packages

Only needed for the developer page scraper. Skip if not using it.

```bash
# Linux / macOS
pip3 install -r requirements.txt

# Windows
pip install -r requirements.txt
```

---

### Step 5 — Run the Dashboard

**Linux / macOS / WSL:**
```bash
python3 apkeep_dashboard.py
```

**Windows CMD / PowerShell:**
```cmd
python apkeep_dashboard.py
```

The dashboard will:
1. Print startup info in your terminal
2. **Auto-open** `http://localhost:8080` in your browser
3. Show whether `apkeep` was detected or not

> If the browser doesn't open automatically, navigate to `http://localhost:8080` manually.

---

---

## 🐳 Docker (Recommended — One Command)

The easiest way to run on any OS. No need to install Python or apkeep manually — Docker handles everything.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / macOS)
- or Docker Engine + Docker Compose plugin (Linux)

```bash
# Verify Docker is installed
docker --version
docker compose version
```

### Run with Docker Compose

```bash
# 1. Clone or download the project files into a folder
# 2. Open a terminal in that folder and run:

docker compose up -d
```

That's it. The dashboard will be available at **http://localhost:8080**

### Useful Docker commands

```bash
# Start in background
docker compose up -d

# Watch live logs
docker compose logs -f

# Stop the container
docker compose down

# Stop and remove volumes (clears downloaded APKs)
docker compose down -v

# Rebuild after code changes
docker compose up -d --build

# Check container status
docker compose ps
```

### Docker output location

Downloaded APKs are saved to a `downloads/` folder **in the same directory** as your `docker-compose.yml`:

```
apkeep-dashboard/
└── downloads/              ← your APKs appear here
    ├── LoopStack_Studio/
    ├── Chromic_Apps/
    └── ...
```

This folder is mounted as a volume so your files persist even if the container is restarted or removed.

> **Note:** The first `docker compose up` will take a few minutes to build — it compiles `apkeep` from source inside the container. Subsequent starts are instant.

---

## 🚀 Quick Start (TL;DR)

```bash
# Complete setup on Linux from scratch

# 1. Install Python
sudo apt install python3 -y

# 2. Install apkeep binary
wget https://github.com/EFForg/apkeep/releases/latest/download/apkeep-x86_64-unknown-linux-gnu
chmod +x apkeep-x86_64-unknown-linux-gnu
sudo mv apkeep-x86_64-unknown-linux-gnu /usr/local/bin/apkeep

# 3. Run the dashboard
python3 apkeep_dashboard.py

# 4. Open browser at http://localhost:8080
```

---

## ✨ Features

### 🎯 Three Download Modes

| Mode | Description |
|---|---|
| **Developer / Studio** | Enter a Play Store developer URL or name — downloads all their apps |
| **Single Package** | Download one APK by package ID or Play Store URL |
| **Bulk Download** | Paste a list, upload a `.txt`/`.csv`, or use the pre-built 148-package list |

### ⚙️ Core Capabilities

- **Live Execution** — actually runs `apkeep` in the background, not just script generation
- **Real-time Terminal** — browser log window shows download progress line by line
- **Progress Bar** — visual indicator showing % complete across all packages
- **Auto-extract** — automatically unzips `.xapk` and `.apks` bundles into raw `.apk` files
- **Auto-organize** — sorts each APK into its own developer-named folder
- **Cross-platform** — works on Linux, Windows, macOS with zero pip dependencies
- **Auto-install apkeep** — if `apkeep` is not found, tries to install via `cargo` automatically
- **Drag & Drop** — drop a `.txt` or `.csv` package list file directly onto the dashboard
- **Pre-loaded list** — 148 packages across 14 developers ready to go in one click

---

## 🖥️ Platform Compatibility

| Platform | Status |
|---|---|
| Linux (Kali, Ubuntu, Debian, etc.) | ✅ Fully supported |
| Windows (CMD, PowerShell, WSL) | ✅ Fully supported |
| macOS (Intel + Apple Silicon) | ✅ Fully supported |
| Android (Termux) | ⚠️ Partial — apkeep supports Termux |

---

## 🗂️ Output Structure

After a bulk download with organize enabled:

```
~/apks_by_developer/
├── LoopStack_Studio/
│   ├── com.lss.sketch.drawing.color.puzzle.brain.game.apk
│   ├── com.lss.flamingo.flying.seabird.bird.parrot.simulator.apk
│   └── ... (20 APKs)
├── Chromic_Apps/
│   └── ... (14 APKs)
├── Crea8iv_Games/
│   └── ... (20 APKs)
├── ... (14 developer folders total)
└── raw_downloads/
    └── (original downloaded files before extraction)
```

---

## 📥 Download Sources

| Source | Flag | Login Required | Notes |
|---|---|---|---|
| **APKPure** | `apk-pure` (default) | ❌ No | Best for free Play Store apps |
| **Google Play** | `google-play` | ✅ Yes (AAS token) | Direct from Google, may flag account |
| **F-Droid** | `f-droid` | ❌ No | Open-source apps only |
| **Huawei AppGallery** | `huawei-app-gallery` | ❌ No | Huawei ecosystem apps |

---

## 📱 Supported File Types

| Format | Description | Handled automatically |
|---|---|---|
| `.apk` | Standard Android app installer | ✅ Moved directly to output |
| `.xapk` | APK + OBB data bundle | ✅ Unzipped, APK extracted |
| `.apks` | Split APK bundle | ✅ Unzipped, all APKs extracted |

---

## 🔧 How It Works

```
Browser UI (http://localhost:8080)
        │
        ▼
Python HTTP Server (apkeep_dashboard.py)
        │
        ├── Parses & validates package IDs from input
        ├── Spawns apkeep subprocess per package
        ├── Streams live logs back to browser
        ├── Extracts XAPK/APKS via Python zipfile module
        └── Organizes APKs into developer folders
```

1. Enter a developer URL, single package ID, or paste/upload a bulk list
2. Python server resolves and validates all package IDs
3. `apkeep` is called for each package pointing to APKPure (or chosen source)
4. Downloaded files land in `raw_downloads/`
5. XAPK/APKS files are automatically unzipped to extract `.apk` files
6. APKs are copied into their respective developer folder
7. Live logs stream to your browser terminal in real-time

---

## 📦 Pre-loaded Package List

Comes with **148 packages** across **14 developers** built-in (from `packages.txt`):

| Developer | Packages |
|---|---|
| LoopStack Studio | 20 |
| Crea8iv Games | 20 |
| Chromic Apps | 14 |
| Micro Madness | 14 |
| Games Rack Studio | 10 |
| Vroom Apps & Games | 10 |
| 360 Pixel Studio | 10 |
| The Game School | 10 |
| Pixels Pioneer | 9 |
| Pro Gaming Studio | 8 |
| MNK Games | 7 |
| Peak Gaming Studio | 6 |
| Gamex Global | 6 |
| Grandeur Gamers | 4 |
| **Total** | **148** |

---

## 📝 Bulk Input Formats

**Plain text — one per line:**
```
com.example.game1
com.example.game2
com.example.game3
```

**Comma separated:**
```
com.example.game1, com.example.game2, com.example.game3
```

**With comments (lines starting with `#` are ignored):**
```
# Studio 1
com.example.game1
com.example.game2

# Studio 2
com.example.game3
```

**Play Store URLs:**
```
https://play.google.com/store/apps/details?id=com.example.game1
```

**CSV file:** Any `.csv` with package IDs in the first column.

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `apkeep not found` | Download binary from [releases](https://github.com/EFForg/apkeep/releases) or run `cargo install apkeep` |
| `cargo not found` | Install Rust first from [rustup.rs](https://rustup.rs) |
| `python3 not found` on Windows | Use `python` instead, or reinstall Python with "Add to PATH" checked |
| Port 8080 already in use | Edit `PORT = 8080` at the bottom of `apkeep_dashboard.py` to e.g. `9090` |
| Browser doesn't open automatically | Go to `http://localhost:8080` manually |
| Download silently fails | Check the terminal log — package may not exist on APKPure |
| XAPK not extracting | Ensure the output directory has write permissions |
| `Permission denied` on Linux | Run `chmod +x apkeep` and make sure it is in your PATH |
| Slow downloads | Normal — APKPure rate limits large batches |
| `pip` not found | Install with `sudo apt install python3-pip` on Linux |

---

## ⚠️ Notes & Limitations

- **APKPure** is a third-party mirror — APKs may be slightly behind the latest Play Store version
- **Paid apps** cannot be downloaded — they will fail and be skipped automatically
- **Google Play source** requires an AAS token and may risk account termination per Google's ToS
- Be respectful of APKPure's servers — avoid extremely rapid bulk requests
- Intended for **academic and research use**

---

## 📄 License

This dashboard uses [apkeep](https://github.com/EFForg/apkeep) which is MIT licensed by the Electronic Frontier Foundation (EFF). Use responsibly and in accordance with the terms of service of the app store you are downloading from.

---

## 🔗 References

- [apkeep GitHub](https://github.com/EFForg/apkeep)
- [apkeep Releases — pre-built binaries](https://github.com/EFForg/apkeep/releases)
- [Rust / Cargo install](https://rustup.rs)
- [Python Downloads](https://python.org/downloads)
