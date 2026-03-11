from src.config import (
    WEIGHT_SECTOR_FIT,
    WEIGHT_RELATIONSHIP_DEPTH,
    WEIGHT_HALO_VALUE,
    WEIGHT_EMERGING_FIT,
    TIER_PRIORITY_CLOSE,
    TIER_STRONG_FIT,
    TIER_MODERATE_FIT,
    CHECK_SIZE_ALLOCATION,
)


def compute_composite(sector_fit: float, relationship_depth: float,
                      halo_value: float, emerging_fit: float) -> float:
    return round(
        sector_fit * WEIGHT_SECTOR_FIT
        + relationship_depth * WEIGHT_RELATIONSHIP_DEPTH
        + halo_value * WEIGHT_HALO_VALUE
        + emerging_fit * WEIGHT_EMERGING_FIT,
        2,
    )


def classify_tier(composite: float) -> str:
    if composite >= TIER_PRIORITY_CLOSE:
        return "PRIORITY CLOSE"
    elif composite >= TIER_STRONG_FIT:
        return "STRONG FIT"
    elif composite >= TIER_MODERATE_FIT:
        return "MODERATE FIT"
    else:
        return "WEAK FIT"


def estimate_check_size(aum_str: str, org_type: str) -> tuple[float | None, float | None]:
    """Parse AUM string and estimate check size range based on org type allocation %."""
    aum = _parse_aum(aum_str)
    if aum is None:
        return None, None

    alloc_range = CHECK_SIZE_ALLOCATION.get(org_type)
    if not alloc_range:
        alloc_range = (0.01, 0.05)

    low_pct, high_pct = alloc_range
    return round(aum * low_pct, 2), round(aum * high_pct, 2)


def _parse_aum(aum_str: str) -> float | None:
    """Best-effort parse of AUM strings like '$6.4B', '~$2 billion', '$500M', 'Unknown'."""
    if not aum_str or aum_str.lower() in ("unknown", "n/a", "none", ""):
        return None

    text = aum_str.replace(",", "").replace("$", "").replace("~", "").replace("approx.", "").strip().lower()

    multiplier = 1.0
    if "trillion" in text or text.endswith("t"):
        multiplier = 1_000_000_000_000
        text = text.replace("trillion", "").replace("t", "").strip()
    elif "billion" in text or text.endswith("b"):
        multiplier = 1_000_000_000
        text = text.replace("billion", "").replace("b", "").strip()
    elif "million" in text or text.endswith("m"):
        multiplier = 1_000_000
        text = text.replace("million", "").replace("m", "").strip()

    try:
        value = float(text.split()[0] if " " in text else text)
        return value * multiplier
    except (ValueError, IndexError):
        return None
