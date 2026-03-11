import logging

logger = logging.getLogger(__name__)

CALIBRATION_ANCHORS = {
    "The Rockefeller Foundation": {
        "org_type": "Foundation",
        "sector_fit": 9,
        "halo_value": 9,
        "emerging_fit": 8,
    },
    "Pension Boards United Church of Christ": {
        "org_type": "Pension",
        "sector_fit": 8,
        "halo_value": 6,
        "emerging_fit": 8,
    },
    "PBUCC": {
        "org_type": "Pension",
        "sector_fit": 8,
        "halo_value": 6,
        "emerging_fit": 8,
    },
    "Inherent Group": {
        "org_type": "Single Family Office",
        "sector_fit": 8,
        "halo_value": 3,
        "emerging_fit": 5,
    },
    "Meridian Capital Group LLC": {
        "org_type": "RIA/FIA",
        "sector_fit": 1,
        "halo_value": 3,
        "emerging_fit": 1,
    },
}

ANOMALY_TOLERANCE = 2.0


def validate_against_anchors(scores_by_org: dict[str, dict]) -> list[dict]:
    """Compare scored results against calibration anchors.
    Returns a list of deviations found."""
    deviations = []

    for org_name, expected in CALIBRATION_ANCHORS.items():
        actual = scores_by_org.get(org_name)
        if not actual:
            continue

        for dim in ("sector_fit", "halo_value", "emerging_fit"):
            expected_val = expected[dim]
            actual_val = actual.get(dim, 4)
            diff = abs(actual_val - expected_val)

            if diff > ANOMALY_TOLERANCE:
                deviation = {
                    "organization": org_name,
                    "dimension": dim,
                    "expected": expected_val,
                    "actual": actual_val,
                    "deviation": diff,
                    "severity": "HIGH" if diff > 3 else "MEDIUM",
                }
                deviations.append(deviation)
                logger.warning(
                    f"CALIBRATION DRIFT: {org_name} {dim} expected={expected_val} "
                    f"actual={actual_val} (deviation={diff})"
                )

    return deviations


def detect_anomalies(org_name: str, org_type: str, is_lp: str,
                     sector_fit: float, halo_value: float,
                     emerging_fit: float) -> str | None:
    """Flag scoring anomalies based on logical rules."""
    flags = []

    gp_types = {"Asset Manager", "Private Capital Firm", "RIA/FIA"}
    if is_lp == "No" and sector_fit > 5:
        flags.append(f"Non-LP ({is_lp}) scored {sector_fit} on Sector Fit — should be ≤2")

    if org_type in gp_types and is_lp == "No" and sector_fit > 3:
        flags.append(f"{org_type} identified as non-LP but Sector Fit={sector_fit}")

    institutional_types = {"Foundation", "Endowment", "Pension"}
    if org_type in institutional_types and sector_fit < 4:
        flags.append(f"{org_type} scored only {sector_fit} on Sector Fit — may be under-researched")

    if is_lp == "No" and emerging_fit > 3:
        flags.append(f"Non-LP scored {emerging_fit} on Emerging Fit")

    return " | ".join(flags) if flags else None
