#!/usr/bin/env bash
# Preseed a fully-worked historical analysis for demo recordings — run this
# once, right before you hit record, so the Version History / Chat beat has
# real depth without a second live LLM call.
#
# Usage:
#   ./scripts/seed_demo_data.sh                         # targets the HF Space
#   PRISM_URL=http://localhost:8002 ./scripts/seed_demo_data.sh   # local docker-compose
#
# Requires ENABLE_DEMO_SEED=true on the target (already set on the HF Space;
# add it to .env for local use). Idempotent — safe to re-run before every take.

set -euo pipefail

PRISM_URL="${PRISM_URL:-https://kapilmanchanda-prism.hf.space}"

echo "Seeding demo data at ${PRISM_URL} ..."

RESPONSE=$(curl -sf -X POST "${PRISM_URL}/admin/seed-demo")

echo "$RESPONSE" | python3 -m json.tool

ANALYSIS_ID=$(echo "$RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['analysis_id'])")

echo ""
echo "Seeded analysis ready at: ${PRISM_URL}/analysis/${ANALYSIS_ID}"
echo "Use this URL for the Version History beat in the demo script."
