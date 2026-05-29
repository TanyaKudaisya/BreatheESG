"""
Django management command: seed_db

Creates test tenants, users, and ingests sample data for development and
evaluation purposes.

Usage:
    python manage.py seed_db

The command is idempotent — running it multiple times will not create
duplicate tenants or users (uses get_or_create throughout).

Requirements: 1.1, 23.3
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand

# Base directory of the Django project (three levels up from this file:
# commands/ → management/ → emissions/ → project root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

SAMPLE_DATA_DIR = BASE_DIR / "sample_data"


class Command(BaseCommand):
    help = "Seed the database with test tenants, users, and sample emission data."

    def handle(self, *args, **options) -> None:
        from emissions.models import Tenant, User
        from ingestion.ingestion_engine import IngestionEngine

        self.stdout.write(self.style.MIGRATE_HEADING("=== Breathe ESG Database Seed ===\n"))

        # ------------------------------------------------------------------
        # 1. Create tenants
        # ------------------------------------------------------------------
        self.stdout.write("Creating tenants...")

        acme, acme_created = Tenant.objects.get_or_create(
            code="ACME",
            defaults={"name": "Acme Corp"},
        )
        beta, beta_created = Tenant.objects.get_or_create(
            code="BETA",
            defaults={"name": "Beta Industries"},
        )

        self.stdout.write(
            f"  {'Created' if acme_created else 'Found'} tenant: {acme}"
        )
        self.stdout.write(
            f"  {'Created' if beta_created else 'Found'} tenant: {beta}"
        )

        # ------------------------------------------------------------------
        # 2. Create users
        # ------------------------------------------------------------------
        self.stdout.write("\nCreating users...")

        users_spec = [
            # (email, password, role, tenant)
            ("analyst@acme.com", "testpass123", User.ROLE_ANALYST, acme),
            ("auditor@acme.com", "testpass123", User.ROLE_AUDITOR, acme),
            ("analyst@beta.com", "testpass123", User.ROLE_ANALYST, beta),
            ("auditor@beta.com", "testpass123", User.ROLE_AUDITOR, beta),
        ]

        created_users = []
        for email, password, role, tenant in users_spec:
            user, user_created = User.objects.get_or_create(
                username=email,
                defaults={
                    "email": email,
                    "role": role,
                    "tenant": tenant,
                    "is_active": True,
                },
            )
            if user_created:
                user.set_password(password)
                user.save(update_fields=["password"])
            created_users.append((user, user_created))
            self.stdout.write(
                f"  {'Created' if user_created else 'Found'} user: {email} "
                f"(role={role}, tenant={tenant.code})"
            )

        # ------------------------------------------------------------------
        # 3. Ingest sample data for Acme Corp
        # ------------------------------------------------------------------
        self.stdout.write(f"\nIngesting sample data for {acme.name}...")

        engine = IngestionEngine()
        tenant_id = str(acme.id)

        # SAP fuel procurement
        sap_file = SAMPLE_DATA_DIR / "sap_fuel_procurement.txt"
        if sap_file.exists():
            content = sap_file.read_bytes()
            result = engine.ingest_sap_file(content, sap_file.name, tenant_id)
            self.stdout.write(
                f"  SAP ({sap_file.name}): "
                f"parsed={result.records_parsed}, "
                f"ingested={result.records_ingested}, "
                f"errors={result.records_with_errors}"
            )
            if result.errors:
                for err in result.errors[:5]:
                    self.stdout.write(
                        self.style.WARNING(f"    Warning: {err.message}")
                    )
                if len(result.errors) > 5:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    ... and {len(result.errors) - 5} more errors"
                        )
                    )
        else:
            self.stdout.write(
                self.style.WARNING(f"  SAP sample file not found: {sap_file}")
            )

        # Utility electricity
        utility_file = SAMPLE_DATA_DIR / "utility_electricity.csv"
        if utility_file.exists():
            content = utility_file.read_bytes()
            result = engine.ingest_utility_file(content, utility_file.name, tenant_id)
            self.stdout.write(
                f"  Utility ({utility_file.name}): "
                f"parsed={result.records_parsed}, "
                f"ingested={result.records_ingested}, "
                f"errors={result.records_with_errors}"
            )
            if result.errors:
                for err in result.errors[:5]:
                    self.stdout.write(
                        self.style.WARNING(f"    Warning: {err.message}")
                    )
        else:
            self.stdout.write(
                self.style.WARNING(f"  Utility sample file not found: {utility_file}")
            )

        # Concur travel
        travel_file = SAMPLE_DATA_DIR / "concur_travel_export.json"
        if travel_file.exists():
            payload = json.loads(travel_file.read_text(encoding="utf-8"))
            result = engine.ingest_travel_json(payload, tenant_id)
            self.stdout.write(
                f"  Travel ({travel_file.name}): "
                f"parsed={result.records_parsed}, "
                f"ingested={result.records_ingested}, "
                f"errors={result.records_with_errors}"
            )
            if result.errors:
                for err in result.errors[:5]:
                    self.stdout.write(
                        self.style.WARNING(f"    Warning: {err.message}")
                    )
        else:
            self.stdout.write(
                self.style.WARNING(f"  Travel sample file not found: {travel_file}")
            )

        # ------------------------------------------------------------------
        # 4. Summary
        # ------------------------------------------------------------------
        from emissions.models import EmissionRecord, DataQualityFlag

        acme_records = EmissionRecord._default_manager.filter(tenant=acme).count()
        acme_flags = DataQualityFlag.objects.filter(
            emission_record__tenant=acme
        ).count()

        self.stdout.write(self.style.SUCCESS("\n=== Seed Summary ==="))
        self.stdout.write(f"  Tenants:          Acme Corp (ACME), Beta Industries (BETA)")
        self.stdout.write(f"  Users created:    {sum(1 for _, c in created_users if c)}")
        self.stdout.write(f"  Users total:      {len(created_users)}")
        self.stdout.write(f"  Acme records:     {acme_records}")
        self.stdout.write(f"  Acme DQ flags:    {acme_flags}")
        self.stdout.write(self.style.SUCCESS("\nDatabase seeded successfully."))
