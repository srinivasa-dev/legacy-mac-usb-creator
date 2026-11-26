#!/usr/bin/env bash
# ==============================================================================
# Legacy macOS USB Creator - Zero-Friction Bootstrap Runner
# One-liner execution:
#   curl -fsSL https://raw.githubusercontent.com/srinivasa-dev/legacy-mac-usb-creator/main/run.sh | sudo bash
# ==============================================================================

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}"
cat << 'EOF'
 ┌───────────────────────────────────────────────────────────────┐
 │   _                                                        _  │
 │  | |    ___  __ _  __ _  ___ _   _   _ __ ___   __ _  ___ | | │
 │  | |   / _ \/ _` |/ _` |/ __| | | | | '_ ` _ \ / _` |/ __|| | │
 │  | |__|  __/ (_| | (_| | (__| |_| |_| | | | | | (_| | (__ |_| │
 │  |_____\___|\__, |\__,_|\___|\__, (_)_| |_| |_|\__,_|\___|(_) │
 │             |___/            |___/                            │
 │            LEGACY INTEL MACOS BOOTABLE USB CREATOR            │
 └───────────────────────────────────────────────────────────────┘
EOF
echo -e "${NC}"

# Check root privileges
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[ERROR] This script must be run as root.${NC}"
    echo -e "Please re-run using sudo:"
    echo -e "  ${YELLOW}curl -fsSL https://raw.githubusercontent.com/srinivasa-dev/legacy-mac-usb-creator/main/run.sh | sudo bash${NC}\n"
    exit 1
fi

# Check Darwin OS
if [[ "$(uname -s)" != "Darwin" ]]; then
    echo -e "${RED}[ERROR] This tool must be run on macOS.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Host OS: macOS ($(uname -m))${NC}"

# Ensure Rosetta 2 if on Apple Silicon
ARCH="$(uname -m)"
if [[ "$ARCH" == "arm64" ]]; then
    if ! /usr/bin/pgrep oahd >/dev/null 2>&1 && ! arch -x86_64 /usr/bin/true 2>/dev/null; then
        echo -e "${YELLOW}[INFO] Installing Rosetta 2 for Intel binary translation...${NC}"
        /usr/sbin/softwareupdate --install-rosetta --agree-to-license || true
    fi
    echo -e "${GREEN}✓ Rosetta 2 environment is active.${NC}"
fi

# Check Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] python3 not found. Please install Xcode Command Line Tools: xcode-select --install${NC}"
    exit 1
fi

# Detect USB drive
TARGET_VOLUME="${1:-/Volumes/MyVolume}"
if [[ ! -d "$TARGET_VOLUME" ]]; then
    if [[ -d "/Volumes/OS X Base System" ]]; then
        TARGET_VOLUME="/Volumes/OS X Base System"
    else
        echo -e "${YELLOW}[WARNING] Target volume '${TARGET_VOLUME}' not found.${NC}"
        echo -e "Detected mounted volumes in /Volumes:"
        ls -1 /Volumes
        echo -e "\nPlease insert your USB drive (32GB+) formatted as 'MyVolume' in Disk Utility."
        echo -e "Or pass volume path as argument: sudo bash run.sh /Volumes/<VolumeName>\n"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Target USB volume found: ${TARGET_VOLUME}${NC}"

# Download or run the core Python script
TMP_SCRIPT="/private/tmp/legacy_macos_usb.py"
REPO_RAW_URL="https://raw.githubusercontent.com/srinivasa-dev/legacy-mac-usb-creator/main/legacy_macos_usb.py"

# If running locally from cloned repo, use local script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/legacy_macos_usb.py" ]]; then
    PYTHON_SCRIPT="${SCRIPT_DIR}/legacy_macos_usb.py"
else
    echo -e "${CYAN}[INFO] Fetching latest legacy_macos_usb.py from GitHub...${NC}"
    curl -fsSL "$REPO_RAW_URL" -o "$TMP_SCRIPT"
    PYTHON_SCRIPT="$TMP_SCRIPT"
fi

echo -e "${GREEN}✓ Launching Legacy macOS USB Creator engine...${NC}\n"
python3 "$PYTHON_SCRIPT" --volume "$TARGET_VOLUME"
