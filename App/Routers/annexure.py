# App/Routers/annexure.py
from fastapi import APIRouter

router = APIRouter(prefix="/annexure", tags=["Annexure"])

ANNEXURE = {
    "exchange_segments": {
        "IDX_I": 0,
        "NSE_EQ": 1,
        "NSE_FNO": 2,
        "NSE_CURRENCY": 3,
        "BSE_EQ": 4,
        "MCX_COMM": 5,
        "BSE_CURRENCY": 7,
        "BSE_FNO": 8,
    },
    "product_types": ["CNC", "INTRADAY", "MARGIN", "CO", "BO"],
    "expiry_codes": {0: "Current", 1: "Next", 2: "Far"},
    "instrument_types": [
        "INDEX", "FUTIDX", "OPTIDX", "EQUITY",
        "FUTSTK", "OPTSTK", "FUTCOM", "OPTFUT", "FUTCUR", "OPTCUR"
    ],
    "feed_request_codes": {
        11: "Connect Feed",
        12: "Disconnect Feed",
        15: "Subscribe - Ticker",
        16: "Unsubscribe - Ticker",
        17: "Subscribe - Quote",
        18: "Unsubscribe - Quote",
        21: "Subscribe - Full",
        22: "Unsubscribe - Full",
        23: "Subscribe - 20 Depth",
        24: "Unsubscribe - 20 Depth",
    },
    "feed_response_codes": {
        1: "Index Packet",
        2: "Ticker Packet",
        4: "Quote Packet",
        5: "OI Packet",
        6: "Prev Close Packet",
        7: "Market Status Packet",
        8: "Full Packet",
        50: "Feed Disconnect",
    },
    "trading_api_errors": {
        "DH-901": "Invalid Authentication",
        "DH-902": "Invalid Access",
        "DH-903": "User Account issue",
        "DH-904": "Rate Limit exceeded",
        "DH-905": "Input Exception",
        "DH-906": "Order Error",
        "DH-907": "Data Error",
        "DH-908": "Internal Server Error",
        "DH-909": "Network Error",
        "DH-910": "Others",
    },
    "data_api_errors": {
        800: "Internal Server Error",
        804: "Too many instruments",
        805: "Too many requests or connections",
        806: "Data APIs not subscribed",
        807: "Access token expired",
        808: "Authentication failed",
        809: "Access token invalid",
        810: "Client ID invalid",
        811: "Invalid Expiry Date",
        812: "Invalid Date Format",
        813: "Invalid SecurityId",
        814: "Invalid Request",
    },
}

@router.get("")
async def get_annexure():
    """Return static Annexure enums & codes (from Dhan docs)."""
    return {"status": "success", "data": ANNEXURE}
