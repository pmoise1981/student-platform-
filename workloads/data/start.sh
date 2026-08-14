#!/usr/bin/env bash
set -euo pipefail

WORK=/home/jovyan/work
mkdir -p "$WORK"
if [ ! -f "$WORK/.initialized" ]; then
  cp -R /opt/student-template/starter/. "$WORK/"
  touch "$WORK/.initialized"
fi

exec start-notebook.py --ServerApp.token="$JUPYTER_TOKEN" --ServerApp.ip=0.0.0.0 --ServerApp.port=8888 --ServerApp.open_browser=False
