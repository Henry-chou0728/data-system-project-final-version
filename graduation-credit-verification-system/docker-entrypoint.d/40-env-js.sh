#!/bin/sh
set -eu

cat > /usr/share/nginx/html/env.js <<EOF
window.__APP_CONFIG__ = { VITE_API_URL: "${VITE_API_URL:-}" };
EOF
