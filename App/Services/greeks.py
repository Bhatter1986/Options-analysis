# App/Services/greeks.py
import math

def _nd(x):  # standard normal pdf
    return (1.0 / math.sqrt(2*math.pi)) * math.exp(-0.5 * x * x)

def _ncdf(x):  # standard normal cdf (erf based)
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2)))

def bs_greeks(spot, strike, iv, t_years, r=0.06, q=0.0):
    """
    Returns dict with delta/gamma/theta/vega for CALL and PUT.
    spot, strike: floats
    iv: implied vol in decimal (e.g. 0.14)
    t_years: time to expiry in YEARS (e.g. days/365)
    r: risk-free rate
    q: dividend/idx yield
    """
    if iv <= 0 or t_years <= 0 or spot <= 0 or strike <= 0:
        # return zeros gracefully
        z = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
        return {"call": z.copy(), "put": z.copy()}

    st = iv * math.sqrt(t_years)
    d1 = (math.log(spot/strike) + (r - q + 0.5*iv*iv)*t_years) / st
    d2 = d1 - st
    pdf = _nd(d1)

    # CALL
    call_delta = math.exp(-q*t_years) * _ncdf(d1)
    call_gamma = (math.exp(-q*t_years) * pdf) / (spot * st)
    call_theta = (- (spot * pdf * iv * math.exp(-q*t_years)) / (2*math.sqrt(t_years))
                  - r*strike*math.exp(-r*t_years)*_ncdf(d2)
                  + q*spot*math.exp(-q*t_years)*_ncdf(d1))
    call_vega  = spot * math.exp(-q*t_years) * pdf * math.sqrt(t_years)

    # PUT (put-call symmetry)
    put_delta = call_delta - math.exp(-q*t_years)
    put_gamma = call_gamma
    put_theta = (- (spot * pdf * iv * math.exp(-q*t_years)) / (2*math.sqrt(t_years))
                 + r*strike*math.exp(-r*t_years)*_ncdf(-d2)
                 - q*spot*math.exp(-q*t_years)*_ncdf(-d1))
    put_vega  = call_vega

    # convention: theta per day (optional). Keep per-day to be readable.
    per_day = 365.0
    call_theta /= per_day
    put_theta  /= per_day
    call_vega  /= 100.0  # vega per 1 vol point
    put_vega   /= 100.0

    return {
        "call": {"delta": call_delta, "gamma": call_gamma, "theta": call_theta, "vega": call_vega},
        "put":  {"delta": put_delta,  "gamma": put_gamma,  "theta": put_theta,  "vega": put_vega},
    }
