#!/usr/bin/env python3
"""
Pipeline invariant checker — connects to the database and verifies
critical data integrity invariants for the inVision platform.

Usage:
    PYTHONPATH=apps/api/src python scripts/check_pipeline_invariants.py

Exit codes:
    0  All invariants pass
    1  One or more invariants failed
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        return 1
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)

    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)

    failures: list[str] = []
    checks_passed = 0

    with engine.connect() as conn:
        # INV-1: submitted_at IS NOT NULL implies locked_after_submit = True
        result = conn.execute(text(
            "SELECT COUNT(*) FROM applications WHERE submitted_at IS NOT NULL AND locked_after_submit = false"
        ))
        count = result.scalar()
        if count and count > 0:
            failures.append(f"INV-1 FAIL: {count} submitted apps with locked_after_submit=false")
        else:
            checks_passed += 1
            print("INV-1 PASS: All submitted applications are locked")

        # INV-3: Every submitted application has a commission projection
        result = conn.execute(text("""
            SELECT COUNT(*) FROM applications a
            WHERE a.submitted_at IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM application_commission_projections p
                WHERE p.application_id = a.id
            )
        """))
        count = result.scalar()
        if count and count > 0:
            failures.append(f"INV-3 FAIL: {count} submitted apps without commission projection")
        else:
            checks_passed += 1
            print("INV-3 PASS: All submitted applications have commission projections")

        # INV-4: All required sections exist for submitted applications
        required_sections = [
            "personal", "contact", "education", "achievements_activities",
            "leadership_evidence", "motivation_goals", "growth_journey",
            "internal_test", "social_status_cert", "documents_manifest",
            "consent_agreement",
        ]
        result = conn.execute(text("""
            SELECT a.id, COUNT(DISTINCT s.section_key) as section_count
            FROM applications a
            LEFT JOIN application_section_states s ON s.application_id = a.id AND s.is_complete = true
            WHERE a.submitted_at IS NOT NULL
            GROUP BY a.id
            HAVING COUNT(DISTINCT s.section_key) < :required_count
        """), {"required_count": len(required_sections)})
        rows = result.fetchall()
        if rows:
            failures.append(f"INV-4 WARN: {len(rows)} submitted apps with fewer than {len(required_sections)} complete sections")
        else:
            checks_passed += 1
            print(f"INV-4 PASS: All submitted applications have {len(required_sections)} complete sections")

        # INV-5/6: Every submitted application has stage history entries
        result = conn.execute(text("""
            SELECT COUNT(*) FROM applications a
            WHERE a.submitted_at IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM application_stage_history h
                WHERE h.application_id = a.id
            )
        """))
        count = result.scalar()
        if count and count > 0:
            failures.append(f"INV-5/6 FAIL: {count} submitted apps without stage history")
        else:
            checks_passed += 1
            print("INV-5/6 PASS: All submitted applications have stage history")

        # INV-8: Validation results have matching application_id
        result = conn.execute(text("""
            SELECT COUNT(*) FROM candidate_validation_checks c
            JOIN candidate_validation_runs r ON c.run_id = r.id
            WHERE r.application_id IS NULL
        """))
        count = result.scalar()
        if count and count > 0:
            failures.append(f"INV-8 FAIL: {count} validation checks with NULL application_id on run")
        else:
            checks_passed += 1
            print("INV-8 PASS: All validation results linked to applications")

        # INV-9: Commission projections have non-null candidate names
        result = conn.execute(text("""
            SELECT COUNT(*) FROM application_commission_projections
            WHERE candidate_full_name IS NULL OR candidate_full_name = ''
        """))
        count = result.scalar()
        if count and count > 0:
            failures.append(f"INV-9 FAIL: {count} projections with null/empty candidate name")
        else:
            checks_passed += 1
            print("INV-9 PASS: All commission projections have candidate names")

    print(f"\n{'='*50}")
    print(f"Results: {checks_passed} passed, {len(failures)} failed")
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        return 1
    print("All pipeline invariants verified successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
