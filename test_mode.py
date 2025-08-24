# testmode.py
"""
TEST mode mocks.
If MODE=TEST, main.py will call mock_dispatch() instead of hitting Dhan.
Keep payload shapes SAME as Dhan so FE can be built & verified.
"""

from typing import Any, Dict

def mock_dispatch(method: str, path: str, payload: Any) -> Dict[str, Any]:
    # Normalize
    method = method.upper()
    if path == "/marketfeed/ltp" and method == "POST":
        return {
            "ticker_data": [
                {"exchangeSegment":"NSE_EQ","securityId":1333,"ltp":1905.5},
                {"exchangeSegment":"NSE_FNO","securityId":52175,"ltp":122.35},
            ]
        }

    if path == "/marketfeed/ohlc" and method == "POST":
        return {
            "ohlc_data":[
                {"exchangeSegment":"NSE_EQ","securityId":1333,"open":1890,"high":1910,"low":1880,"close":1902,"ltp":1901.8}
            ]
        }

    if path == "/marketfeed/quote" and method == "POST":
        return {
            "quote_data":[
                {
                    "exchangeSegment":"NSE_EQ","securityId":1333,
                    "best_bid_price":1901.5,"best_bid_qty":250,
                    "best_ask_price":1902.0,"best_ask_qty":300,
                    "oi": None, "volume": 123456
                }
            ]
        }

    if path == "/optionchain/expirylist" and method == "POST":
        return {
            "data": ["2025-08-28","2025-09-04","2025-09-25"],
            "status": "success"
        }

    if path == "/optionchain" and method == "POST":
        expiry = (payload or {}).get("Expiry") or "2025-08-28"
        return {
            "data": {
                "last_price": 24964.25,
                "oc": {
                    "25000.000000": {
                        "ce": {
                            "greeks":{"delta":0.52,"theta":-12.8,"gamma":0.0013,"vega":13.0},
                            "implied_volatility": 9.0,
                            "last_price": 125.05,
                            "oi": 5962675,
                            "previous_close_price": 190.45,
                            "previous_oi": 3939375,
                            "previous_volume": 831463,
                            "top_ask_price": 124.9,
                            "top_ask_quantity": 1000,
                            "top_bid_price": 124.0,
                            "top_bid_quantity": 100,
                            "volume": 84202625
                        },
                        "pe": {
                            "greeks":{"delta":-0.48,"theta":-10.5,"gamma":0.0009,"vega":13.0},
                            "implied_volatility": 13.3,
                            "last_price": 165.0,
                            "oi": 5059700,
                            "previous_close_price": 153.6,
                            "previous_oi": 4667700,
                            "previous_volume": 1047989,
                            "top_ask_price": 165.0,
                            "top_ask_quantity": 375,
                            "top_bid_price": 164.05,
                            "top_bid_quantity": 50,
                            "volume": 81097175
                        }
                    }
                }
            },
            "requested_expiry": expiry
        }

    if path == "/orders" and method == "GET":
        return [{"orderId":"MOCK123","orderStatus":"PENDING","securityId":"1333","quantity":10,"price":0,"orderType":"MARKET"}]

    if path == "/positions" and method == "GET":
        return [{"tradingSymbol":"HDFCBANK","securityId":"1333","positionType":"LONG","netQty":10,"buyAvg":1900.0}]

    if path == "/holdings" and method == "GET":
        return [{"exchange":"NSE","tradingSymbol":"HDFCBANK","securityId":"1333","totalQty":10,"avgCostPrice":1800.0,"lastTradedPrice":1902.0}]

    if path == "/funds" and method == "GET":
        return {"availabelBalance": 250000.0, "utilizedAmount": 5000.0, "withdrawableBalance": 245000.0}

    if path == "/charts/intraday" and method == "POST":
        return {
            "open":[1895,1898,1900],
            "high":[1905,1906,1908],
            "low":[1890,1892,1897],
            "close":[1898,1901,1906],
            "volume":[10000,12000,15000],
            "timestamp":[int(1.0e9)+i*60 for i in range(3)]
        }

    if path == "/charts/historical" and method == "POST":
        return {
            "open":[1800,1850,1880],
            "high":[1860,1890,1920],
            "low":[1780,1830,1860],
            "close":[1850,1885,1910],
            "volume":[1_000_000, 900_000, 1_200_000],
            "timestamp":[int(1.6e9), int(1.6e9)+86400, int(1.6e9)+2*86400]
        }

    # default
    return {"note":"No mock defined for this path/method yet","path":path,"method":method,"payload":payload}
