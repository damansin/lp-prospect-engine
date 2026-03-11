import logging
import pandas as pd
from sqlalchemy.orm import Session
from src.models import Organization, Contact

logger = logging.getLogger(__name__)


def load_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()

    required = {"Contact Name", "Organization", "Org Type", "Role",
                "Email", "Region", "Contact Status", "Relationship Depth"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    df = df.dropna(subset=["Contact Name", "Organization"], how="all")
    df = df[df["Contact Name"].str.strip().astype(bool)]

    df["Relationship Depth"] = pd.to_numeric(df["Relationship Depth"], errors="coerce").fillna(4).astype(int)
    df["Relationship Depth"] = df["Relationship Depth"].clip(1, 10)

    for col in ["Contact Name", "Organization", "Org Type", "Role", "Email", "Region", "Contact Status"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    logger.info(f"Loaded {len(df)} valid contacts from CSV")
    return df


def ingest_to_db(session: Session, df: pd.DataFrame) -> dict:
    stats = {"orgs_created": 0, "orgs_existing": 0, "contacts_created": 0, "contacts_skipped": 0}

    org_cache: dict[str, Organization] = {}

    existing_orgs = session.query(Organization).all()
    for org in existing_orgs:
        org_cache[org.name.lower()] = org

    existing_contacts = set()
    for c in session.query(Contact.name, Contact.organization_id).all():
        existing_contacts.add((c.name.lower(), c.organization_id))

    for _, row in df.iterrows():
        org_name = row["Organization"]
        org_key = org_name.lower()

        if org_key not in org_cache:
            org = Organization(
                name=org_name,
                org_type=row["Org Type"],
                region=row["Region"],
                enrichment_status="pending",
            )
            session.add(org)
            session.flush()
            org_cache[org_key] = org
            stats["orgs_created"] += 1
        else:
            org = org_cache[org_key]
            stats["orgs_existing"] += 1

        if (row["Contact Name"].lower(), org.id) in existing_contacts:
            stats["contacts_skipped"] += 1
            continue

        contact = Contact(
            name=row["Contact Name"],
            organization_id=org.id,
            role=row["Role"],
            email=row["Email"],
            contact_status=row["Contact Status"],
            relationship_depth=row["Relationship Depth"],
        )
        session.add(contact)
        existing_contacts.add((row["Contact Name"].lower(), org.id))
        stats["contacts_created"] += 1

    session.commit()
    logger.info(
        f"Ingestion complete: {stats['orgs_created']} new orgs, "
        f"{stats['contacts_created']} new contacts, "
        f"{stats['contacts_skipped']} skipped (duplicates)"
    )
    return stats
