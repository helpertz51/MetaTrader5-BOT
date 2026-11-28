#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/helpertz51/ICT_Library_MQ5.git"
WORK_DIR="${TMPDIR:-/tmp}/ICT_Library_MQ5"
MT5_DATA_DIR="${1:-}"

if [[ -z "$MT5_DATA_DIR" ]]; then
  echo "Usage: $0 /path/to/MT5/MQL5"
  exit 2
fi
if [[ ! -d "$MT5_DATA_DIR" ]]; then
  echo "MT5 data directory does not exist: $MT5_DATA_DIR"
  exit 2
fi

if [[ -d "$WORK_DIR/.git" ]]; then
  git -C "$WORK_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$WORK_DIR"
fi

mkdir -p "$MT5_DATA_DIR/Include/SMC" "$MT5_DATA_DIR/Experts"
cp -R "$WORK_DIR/Include/SMC/." "$MT5_DATA_DIR/Include/SMC/"
cp "$WORK_DIR/Experts/SMC_Snapshot_Export.mq5" "$MT5_DATA_DIR/Experts/"
echo "ICT SMC files copied. Open MetaEditor and compile SMC_Snapshot_Export.mq5."
echo "This exporter is data-only; it does not send trade orders."
