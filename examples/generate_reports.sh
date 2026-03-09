#!/usr/bin/env bash
# Generate HTML reports from example doctor JSONs
set -euo pipefail
cd "$(dirname "$0")/.."
for json in examples/fusion-doctor-report-*.json; do
    html="${json%.json}.html"
    uv run --no-project --script bin/generate_fusion_report.py \
        --doctor "$json" --output-html "$html" --output-json /dev/null
    echo "$html"
done
