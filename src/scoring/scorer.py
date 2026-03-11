import json
import logging
from sqlalchemy.orm import Session
from src.models import Organization, Contact, Score
from src.scoring.dimensions import compute_composite, classify_tier, estimate_check_size
from src.scoring.calibration import detect_anomalies, validate_against_anchors
from src.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class ScoringEngine:
    def __init__(self, session: Session, cost_tracker: CostTracker | None = None):
        self.session = session
        self.cost_tracker = cost_tracker

    def score_all(self) -> dict:
        """Score all contacts whose organizations have been enriched."""
        contacts = (
            self.session.query(Contact)
            .join(Organization)
            .filter(Organization.enrichment_status == "done")
            .all()
        )

        stats = {"total": len(contacts), "scored": 0, "skipped": 0, "anomalies": 0}
        scores_by_org: dict[str, dict] = {}

        for contact in contacts:
            existing = self.session.query(Score).filter_by(contact_id=contact.id).first()
            if existing:
                stats["skipped"] += 1
                continue

            org = contact.organization
            enrichment = self._parse_enrichment(org)
            if not enrichment:
                stats["skipped"] += 1
                continue

            sector_fit = float(enrichment.get("sector_fit_score", 4))
            relationship_depth = float(contact.relationship_depth or 4)
            halo_value = float(enrichment.get("halo_value_score", 4))
            emerging_fit = float(enrichment.get("emerging_fit_score", 4))

            composite = compute_composite(sector_fit, relationship_depth, halo_value, emerging_fit)
            tier = classify_tier(composite)

            check_low, check_high = estimate_check_size(
                org.aum_estimated or "Unknown", org.org_type or ""
            )

            anomaly = detect_anomalies(
                org.name, org.org_type or "", org.is_lp or "Unclear",
                sector_fit, halo_value, emerging_fit,
            )
            if anomaly:
                stats["anomalies"] += 1

            score = Score(
                contact_id=contact.id,
                organization_id=org.id,
                sector_fit=sector_fit,
                sector_fit_reasoning=enrichment.get("sector_fit_reasoning", ""),
                sector_fit_confidence=enrichment.get("sector_fit_confidence", "Low"),
                relationship_depth=relationship_depth,
                halo_value=halo_value,
                halo_reasoning=enrichment.get("halo_reasoning", ""),
                halo_confidence=enrichment.get("halo_confidence", "Low"),
                emerging_fit=emerging_fit,
                emerging_reasoning=enrichment.get("emerging_fit_reasoning", ""),
                emerging_confidence=enrichment.get("emerging_fit_confidence", "Low"),
                composite_score=composite,
                tier=tier,
                check_size_low=check_low,
                check_size_high=check_high,
                is_anomaly=anomaly,
            )
            self.session.add(score)
            stats["scored"] += 1

            scores_by_org[org.name] = {
                "sector_fit": sector_fit,
                "halo_value": halo_value,
                "emerging_fit": emerging_fit,
            }

            logger.debug(
                f"  {contact.name} @ {org.name}: "
                f"S={sector_fit} R={relationship_depth} H={halo_value} E={emerging_fit} "
                f"→ Composite={composite} ({tier})"
            )

        self.session.commit()

        calibration_deviations = validate_against_anchors(scores_by_org)
        if calibration_deviations:
            stats["calibration_deviations"] = calibration_deviations

        logger.info(
            f"Scoring complete: {stats['scored']} scored, "
            f"{stats['skipped']} skipped, {stats['anomalies']} anomalies"
        )
        return stats

    def _parse_enrichment(self, org: Organization) -> dict | None:
        if not org.enrichment_data:
            return None
        try:
            return json.loads(org.enrichment_data)
        except json.JSONDecodeError:
            logger.error(f"Could not parse enrichment data for {org.name}")
            return None

    def rescore_contact(self, contact_id: int) -> Score | None:
        """Re-score a specific contact (deletes old score first)."""
        old = self.session.query(Score).filter_by(contact_id=contact_id).first()
        if old:
            self.session.delete(old)
            self.session.commit()

        contact = self.session.query(Contact).get(contact_id)
        if not contact:
            return None

        org = contact.organization
        enrichment = self._parse_enrichment(org)
        if not enrichment:
            return None

        sector_fit = float(enrichment.get("sector_fit_score", 4))
        relationship_depth = float(contact.relationship_depth or 4)
        halo_value = float(enrichment.get("halo_value_score", 4))
        emerging_fit = float(enrichment.get("emerging_fit_score", 4))

        composite = compute_composite(sector_fit, relationship_depth, halo_value, emerging_fit)
        tier = classify_tier(composite)

        check_low, check_high = estimate_check_size(
            org.aum_estimated or "Unknown", org.org_type or ""
        )

        anomaly = detect_anomalies(
            org.name, org.org_type or "", org.is_lp or "Unclear",
            sector_fit, halo_value, emerging_fit,
        )

        score = Score(
            contact_id=contact.id,
            organization_id=org.id,
            sector_fit=sector_fit,
            sector_fit_reasoning=enrichment.get("sector_fit_reasoning", ""),
            sector_fit_confidence=enrichment.get("sector_fit_confidence", "Low"),
            relationship_depth=relationship_depth,
            halo_value=halo_value,
            halo_reasoning=enrichment.get("halo_reasoning", ""),
            halo_confidence=enrichment.get("halo_confidence", "Low"),
            emerging_fit=emerging_fit,
            emerging_reasoning=enrichment.get("emerging_fit_reasoning", ""),
            emerging_confidence=enrichment.get("emerging_fit_confidence", "Low"),
            composite_score=composite,
            tier=tier,
            check_size_low=check_low,
            check_size_high=check_high,
            is_anomaly=anomaly,
        )
        self.session.add(score)
        self.session.commit()
        return score
