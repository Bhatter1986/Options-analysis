# App/sudarshan/engine/fusion.py
def fuse(outputs: dict, weights: dict | None = None, min_confirmations: int = 3):
    keys = ["price", "oi", "greeks", "volume", "sentiment"]
    w = {k: float((weights or {}).get(k, 1.0)) for k in keys}

    per = {}
    total_w = 0.0
    total = 0.0
    confirms = 0

    for k in keys:
        sc = float((outputs.get(k) or {}).get("score", 0.0))
        wk = w[k]
        per[k] = sc * wk
        total += per[k]
        total_w += abs(wk)
        if sc > 0:
            confirms += 1
        elif sc < 0:
            confirms -= 1  # negative confirmation for short bias

    norm = total / total_w if total_w else 0.0

    verdict = "neutral"
    if confirms >= min_confirmations and norm > 0:
        verdict = "long"
    elif confirms <= -min_confirmations and norm < 0:
        verdict = "short"

    return {"per_blade": per, "combined": norm, "confirms": confirms}, verdict
