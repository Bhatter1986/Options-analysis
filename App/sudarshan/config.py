MARKET = dict(
    symbol_underliers=["NIFTY 50","BANKNIFTY"],
    intervals=["5m","15m","1h"],
    start_time="09:15", end_time="15:30",
)

RISK = dict(
    per_trade_risk_pct=0.02,
    daily_loss_cap_pct=0.05,
    max_trades_per_day=3,
    close_all_by="15:00",
)

THETA_IV = dict(
    theta_shield_same_day=False,
    use_next_week_expiry=True,
    ivp_buy_threshold=30,
    ivp_skip_threshold=80,
)

FUSION = dict(
    min_confirmations=3,
    default_weights={"price":1.0,"oi":1.0,"greeks":0.8,"volume":0.7,"sentiment":0.5},
)
