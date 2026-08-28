#!/usr/bin/env bash
set -euo pipefail

name="DJI Clip Color.py"
case "$(uname -s)" in
  Darwin)
    dest="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
    ;;
  Linux)
    dest="${XDG_DATA_HOME:-$HOME/.local/share}/DaVinciResolve/Fusion/Scripts/Utility"
    ;;
  *)
    echo "On Windows run uninstall.bat" >&2
    exit 1
    ;;
esac

target="$dest/$name"
if [[ -f "$target" ]]; then
  rm -f "$target"
  echo "Removed $target"
else
  echo "Nothing to remove ($target)"
fi
