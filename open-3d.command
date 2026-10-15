#!/bin/bash
cd "$(dirname "$0")"; (sleep 1; open "http://localhost:8000/dashboard-cesium.html") & python3 -m http.server 8000
