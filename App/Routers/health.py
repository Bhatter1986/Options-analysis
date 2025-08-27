# Health check
curl -sS "$BASE/health" | jq

# Debug (rows count)
curl -sS "$BASE/instruments/_debug" | jq

# Sample rows
curl -sS "$BASE/instruments" | jq

# Sirf indices
curl -sS "$BASE/instruments/indices?q=nifty" | jq

# Search (Reliance)
curl -sS "$BASE/instruments/search?q=reliance" | jq

# By-ID
curl -sS "$BASE/instruments/by-id?security_id=2" | jq    # NIFTY
curl -sS "$BASE/instruments/by-id?security_id=25" | jq   # BANKNIFTY
curl -sS "$BASE/instruments/by-id?security_id=834804" | jq  # RELIANCE FUT
