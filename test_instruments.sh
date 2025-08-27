#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-https://options-analysis.onrender.com}"

echo "Using BASE=$BASE"

echo
echo "1) Refresh (POST) ..."
curl -sS -X POST "$BASE/instruments/_refresh" | jq

echo
echo "2) Debug ..."
curl -sS "$BASE/instruments/_debug" | jq

echo
echo "3) Sample (first 5) ..."
curl -sS "$BASE/instruments" | jq '.data[0:5]'

echo
echo "4) By-ID (NIFTY=2, BANKNIFTY=25) ..."
echo "- NIFTY:"
curl -sS "$BASE/instruments/by-id?security_id=2" | jq
echo "- BANKNIFTY:"
curl -sS "$BASE/instruments/by-id?security_id=25" | jq
