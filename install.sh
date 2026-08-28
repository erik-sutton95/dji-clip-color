#!/usr/bin/env bash
# Install DJI Clip Color into DaVinci Resolve's Utility scripts folder.
# Safe to run from a clone, a GitHub ZIP, or:
#   curl -fsSL https://raw.githubusercontent.com/erik-sutton95/dji-clip-color/main/install.sh | bash
set -euo pipefail

REPO_SLUG="${DJI_CLIP_COLOR_REPO:-erik-sutton95/dji-clip-color}"
BRANCH="${DJI_CLIP_COLOR_BRANCH:-main}"
RAW_URL="https://raw.githubusercontent.com/${REPO_SLUG}/${BRANCH}/dji_clip_color.py"
SCRIPT_NAME="DJI Clip Color.py"

pause_if_interactive() {
  if [[ -t 0 && -t 1 ]]; then
    echo
    read -r -p "Press Return to close. " _ || true
  fi
}

die() {
  echo "Error: $*" >&2
  pause_if_interactive
  exit 1
}

echo
echo "DJI Clip Color — installer"
echo "=========================="

os="$(uname -s)"
case "$os" in
  Darwin)
    dest="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
    resolve_app="/Applications/DaVinci Resolve/DaVinci Resolve.app"
    ;;
  Linux)
    dest="${XDG_DATA_HOME:-$HOME/.local/share}/DaVinciResolve/Fusion/Scripts/Utility"
    resolve_app=""
    ;;
  MINGW*|MSYS*|CYGWIN*)
    dest="${APPDATA}/Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Utility"
    resolve_app=""
    ;;
  *)
    die "Unsupported OS: $os"
    ;;
esac

src=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ -f "$root/dji_clip_color.py" ]]; then
    src="$root/dji_clip_color.py"
  fi
fi

tmpdir=""
cleanup() {
  if [[ -n "$tmpdir" && -d "$tmpdir" ]]; then
    rm -rf "$tmpdir"
  fi
}
trap cleanup EXIT

if [[ -z "$src" ]]; then
  echo "No local dji_clip_color.py — downloading from GitHub ($REPO_SLUG@$BRANCH)"
  command -v curl >/dev/null 2>&1 || die "curl is required to download the script"
  tmpdir="$(mktemp -d)"
  src="$tmpdir/dji_clip_color.py"
  curl -fsSL "$RAW_URL" -o "$src" || die "download failed: $RAW_URL"
fi

mkdir -p "$dest" || die "could not create $dest"
cp "$src" "$dest/$SCRIPT_NAME" || die "could not copy into $dest"
echo
echo "Installed:"
echo "  $dest/$SCRIPT_NAME"

if [[ "$os" == "Darwin" ]]; then
  if [[ -d "$resolve_app" ]]; then
    echo
    echo "DaVinci Resolve found in /Applications."
  else
    echo
    echo "Note: DaVinci Resolve.app was not in /Applications."
    echo "The script is still installed; open Resolve from wherever you keep it."
  fi
fi

echo
echo "Next:"
echo "  1. Restart DaVinci Resolve if it is already open."
echo "  2. Import original MP4 / MOV takes (not .LRF / .XRF proxies)."
echo "  3. Select clips in the Media Pool."
echo "  4. Workspace > Scripts > DJI Clip Color"
echo "  5. Right-click a Media Pool column header and enable DJI Color."
echo
echo "Clip colors:  Orange = D-Log2   Navy = D-Log   Pink = D-Log M   Teal = HLG"

if [[ "$os" == "Darwin" ]]; then
  open -R "$dest/$SCRIPT_NAME" >/dev/null 2>&1 || true
fi

pause_if_interactive
