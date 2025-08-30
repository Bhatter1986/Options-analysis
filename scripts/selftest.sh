#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-https://options-analysis.onrender.com}"

say(){ echo -e "\n== $* =="; }

say "APP SELFTEST"
curl -sS "$BASE/__selftest" | jq

say "INSTRUMENTS DEBUG (before)"
curl -sS "$BASE/instruments/_debug" | jq

say "REFRESH INSTRUMENTS"
curl -sS -X POST "$BASE/admin/refresh_instruments" | jq || true

say "INSTRUMENTS DEBUG (after)"
curl -sS "$BASE/instruments/_debug" | jq

# BANKNIFTY demo
SID=25
SEG="IDX_I"

say "EXPIRYLIST (BANKNIFTY)"
EXPLIST_JSON=$(curl -sS "$BASE/optionchain/expirylist?under_security_id=$SID&under_exchange_segment=$SEG")
echo "$EXPLIST_JSON" | jq

EXP=$(echo "$EXPLIST_JSON" | jq -r '.data[0] // empty')
if [[ -z "${EXP:-}" || "$EXP" == "null" ]]; then
  echo "No expiry found — exiting"
  exit 1
fi
say "USING EXPIRY: $EXP"
curl -sS "$BASE/optionchain?under_security_id=$SID&under_exchange_segment=$SEG&expiry=$EXP" | jq
