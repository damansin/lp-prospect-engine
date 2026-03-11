"""Export scored results to CSV for submission."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src.database import init_db, get_session
from src.models import Organization, Contact, Score

init_db()
session = get_session()

rows = []
contacts = (
    session.query(Contact)
    .join(Organization)
    .outerjoin(Score, Score.contact_id == Contact.id)
    .all()
)

for c in contacts:
    org = c.organization
    s = c.score
    rows.append({
        "Contact Name": c.name,
        "Organization": org.name,
        "Org Type": org.org_type,
        "Role": c.role,
        "Email": c.email,
        "Region": org.region,
        "Contact Status": c.contact_status,
        "Is LP": org.is_lp or "N/A",
        "AUM (Estimated)": org.aum_estimated or "Unknown",
        "Sector Fit (35%)": s.sector_fit if s else None,
        "Sector Fit Confidence": s.sector_fit_confidence if s else None,
        "Sector Fit Reasoning": s.sector_fit_reasoning if s else None,
        "Relationship Depth (30%)": s.relationship_depth if s else None,
        "Halo Value (20%)": s.halo_value if s else None,
        "Halo Confidence": s.halo_confidence if s else None,
        "Halo Reasoning": s.halo_reasoning if s else None,
        "Emerging Fit (15%)": s.emerging_fit if s else None,
        "Emerging Confidence": s.emerging_confidence if s else None,
        "Emerging Reasoning": s.emerging_reasoning if s else None,
        "Composite Score": s.composite_score if s else None,
        "Tier": s.tier if s else None,
        "Check Size Low ($)": s.check_size_low if s else None,
        "Check Size High ($)": s.check_size_high if s else None,
        "Anomaly Flag": s.is_anomaly if s else None,
    })

df = pd.DataFrame(rows)
df = df.sort_values("Composite Score", ascending=False)

output_path = Path(__file__).resolve().parent.parent / "sample_output.csv"
df.to_csv(output_path, index=False)
print(f"Exported {len(df)} contacts to {output_path}")

print(f"\n{'='*80}")
print("TOP 20 PROSPECTS")
print(f"{'='*80}")
top = df.head(20)
for i, (_, r) in enumerate(top.iterrows(), 1):
    print(f"{i:2d}. {r['Contact Name']:<30s} | {r['Organization']:<40s} | "
          f"Score={r['Composite Score']:.2f} | {r['Tier']}")

print(f"\n{'='*80}")
print("TIER DISTRIBUTION")
print(f"{'='*80}")
print(df["Tier"].value_counts().to_string())

session.close()
