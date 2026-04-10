from fastapi import APIRouter
from app.config import DEFAULT_SYMBOLS

router = APIRouter(prefix="/api", tags=["symbols"])

SYMBOL_CATEGORIES = {
    "VN30": ["VCB", "HPG", "FPT", "VIC", "VHM", "TCB", "MBB", "ACB", "SSI", "VND",
             "GAS", "VNM", "MSN", "MWG", "PLX", "BID", "CTG", "STB", "TPB", "VPB",
             "PDR", "VRE", "GVR", "SAB", "POW", "HDB", "BCM", "SHB", "KDH", "VJC"],
    "INDEX": ["VNINDEX", "VN30", "HNX", "HNXLCAP", "HNXSMCAP", "HNXFIN", "HNX30",
              "UPCOM", "VNXALL"],
}


@router.get("/symbols")
async def list_symbols():
    symbols = [s.strip() for s in DEFAULT_SYMBOLS.split(",") if s.strip()]
    return [
        {"symbol": sym, "name": sym, "type": _get_type(sym)}
        for sym in symbols
    ]


@router.get("/symbols/categories")
async def list_categories():
    return SYMBOL_CATEGORIES


def _get_type(sym: str) -> str:
    if sym.startswith("VN30F"):
        return "derivative"
    if sym in SYMBOL_CATEGORIES.get("INDEX", []):
        return "index"
    return "stock"
