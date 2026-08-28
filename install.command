#!/bin/bash
# Double-click this on a Mac. It opens Terminal and installs DJI Clip Color.
cd "$(dirname "$0")" || exit 1
chmod +x "./install.sh" 2>/dev/null || true
./install.sh
status=$?
if [[ $status -ne 0 ]]; then
  echo
  read -r -p "Install failed. Press Return to close. " _
fi
exit $status
