# Breathe ESG — Data Ingestion System

A multi-tenant enterprise platform for ingesting, normalizing, validating, and reviewing
greenhouse gas emissions activity data from SAP fuel procurement, utility electricity bills,
and Concur corporate travel expenses.

---

## Project Overview

The system ingests heterogeneous emissions data from three source systems, normalizes it
into a unified format, flags data quality issues for analyst review, and maintains a
complete immutable audit trail. It supports multiple client tenants with complete data
isolation.

**Source systems supported:**
- SAP fuel and procurement exports (tab-separated, SE16 format)
- Utility electricity CSV exports (Indian discoms: MSEDCL, TNEB, BESCOM, DGVCL)
- Concur Expense v3 API JSON exports (corporate travel)

**Key capabilities:**
- Automatic GHG Protocol scope classification (Scope 1 / 2 / 3 Category 6)
- Data quality flagging (blank quantities, zero prices, estimated readings, missing receipts)
- Duplicate detection by natural key per source system
- Billing period proportional allocation across calendar months
- Flight distance calculation via Haversine formula from IATA airport codes
- Analyst approval / rejection workflow with audit trail
- Audit lock mechanism for post-approval immutability
- Multi-tenant row-level isolation via TenantManager

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- PostgreSQL 15+ (local instance or Supabase)

### Backend Setup

**1. Clone the repository and create a virtual environment:**

```bash
git clone <repo-url>
cd "breathe esg"
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

**2. Install Python dependencies:**

```bash
pip install -r requirements.txt
```

**3. Configure environment variables:**

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```dotenv
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL — use your local instance or Supabase connection string
DB_NAME=breathe_esg
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432

CORS_ALLOWED_ORIGINS=http://localhost:5173
DJANGO_SETTINGS_MODULE=breathe_esg.settings.development
```

> **Supabase:** If using Supabase, set `DB_HOST` to your Supabase project host,
> `DB_PORT` to `5432`, and use the database password from your Supabase project settings.
> The database is already configured in the provided `.env` file for the deployed instance.

**4. Run database migrations:**

```bash
python manage.py migrate
```

**5. Create a superuser (optional, for Django admin):**

```bash
python manage.py createsuperuser
```

**6. Seed the database with sample data and test tenants:**

```bash
python manage.py seed_db
```

This creates two tenants (`Acme Corp` and `Beta Industries`), analyst and auditor users
for each, and ingests the sample data files from the `docs/` directory.

**7. Start the development server:**

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000/api/v1/`.

---

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The React app will be available at `http://localhost:5173`.

The frontend proxies API requests to `http://localhost:8000` — no CORS configuration
needed for local development.

---

### Running Tests

```bash
# Backend tests
pytest

# Frontend tests
cd frontend
npm test
```

---

## Test Credentials

After running `python manage.py seed_db`, the following accounts are available:

| Username | Password | Tenant | Role |
|----------|----------|--------|------|
| `analyst@acme.com` | `testpass123` | Acme Corp | Analyst |
| `auditor@acme.com` | `testpass123` | Acme Corp | Auditor |
| `analyst@beta.com` | `testpass123` | Beta Industries | Analyst |
| `auditor@beta.com` | `testpass123` | Beta Industries | Auditor |

---

## API Documentation

All endpoints are prefixed with `/api/v1/`. Authentication uses Django session auth;
include the session cookie from the login response in subsequent requests.

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/login/` | Log in, returns session cookie |
| `POST` | `/api/v1/auth/logout/` | Log out |

### Emission Records

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/emissions/` | List emission records (paginated, filterable) |
| `GET` | `/api/v1/emissions/{id}/` | Retrieve a single emission record |
| `PATCH` | `/api/v1/emissions/{id}/` | Edit record fields (quantity, unit, date, location) |
| `POST` | `/api/v1/emissions/{id}/approve/` | Approve a record for audit |
| `POST` | `/api/v1/emissions/{id}/reject/` | Reject a record with a reason |
| `POST` | `/api/v1/emissions/bulk-approve/` | Bulk approve selected records |
| `POST` | `/api/v1/emissions/bulk-reject/` | Bulk reject selected records |
| `POST` | `/api/v1/emissions/{id}/lock/` | Lock a record for audit (immutable) |
| `POST` | `/api/v1/emissions/{id}/unlock/` | Unlock a record (auditor role required) |

**Query parameters for `GET /api/v1/emissions/`:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `source_system` | string | Filter by `SAP`, `UTILITY`, or `CONCUR` |
| `scope` | integer | Filter by scope (1, 2, or 3) |
| `approval_status` | string | Filter by `PENDING`, `APPROVED`, or `REJECTED` |
| `date_from` | date | Filter records on or after this date (YYYY-MM-DD) |
| `date_to` | date | Filter records on or before this date (YYYY-MM-DD) |
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Records per page (default: 50, max: 200) |

### Data Quality Flags

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/quality-flags/` | List all unresolved data quality flags |
| `POST` | `/api/v1/quality-flags/{id}/resolve/` | Mark a flag as resolved |

**Query parameters for `GET /api/v1/quality-flags/`:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `flag_type` | string | Filter by flag type (e.g., `estimated_reading`, `zero_price`) |
| `severity` | string | Filter by `WARNING` or `ERROR` |
| `is_resolved` | boolean | Include resolved flags (default: false) |

### Audit Trail

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/audit-trail/{record_id}/` | Get complete audit trail for a record |

### Data Ingestion

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/ingest/sap/` | Upload SAP tab-separated file (multipart/form-data) |
| `POST` | `/api/v1/ingest/utility/` | Upload utility CSV file (multipart/form-data) |
| `POST` | `/api/v1/ingest/travel/` | Post Concur JSON payload (application/json) |

**Ingestion response format:**

```json
{
  "records_parsed": 12,
  "records_with_errors": 1,
  "records_ingested": 11,
  "errors": [
    {
      "row": 7,
      "message": "Unable to parse date '32/13/2024'"
    }
  ]
}
```

### Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/config/emission-factors/` | Get currently loaded emission factors |
| `GET` | `/api/v1/config/unit-conversions/` | Get unit conversion rates |

---

## Database

The system uses **PostgreSQL 15+**. For the deployed instance, Supabase PostgreSQL is used.

The database connection is configured via environment variables in `.env`. The schema is
managed entirely through Django migrations — no manual SQL setup is required.

**Key tables:**

| Table | Description |
|-------|-------------|
| `emissions_tenant` | Client companies (multi-tenant root) |
| `emissions_user` | Users with tenant association and role |
| `emissions_emissionrecord` | Normalized emission activity records |
| `emissions_dataqualityflag` | Data quality issue markers |
| `emissions_monthlyallocation` | Billing period monthly allocations |
| `audit_auditevent` | Immutable audit trail events |

---

## Project Structure

```
breathe esg/
├── breathe_esg/          # Django project settings and URL config
│   └── settings/
│       ├── base.py
│       ├── development.py
│       └── production.py
├── emissions/            # Core data models, TenantManager, approval workflow
├── ingestion/            # SAP, Utility, and Travel parsers + IngestionEngine
├── normalization/        # Date, unit, and billing period normalization
├── validation/           # Data quality flags and duplicate detection
├── audit/                # AuditTrailStore and AuditEvent model
├── config/               # emission_config.json (emission factors, unit conversions)
├── docs/                 # Sample data files (SAP, utility, Concur, plant lookup)
├── frontend/             # React 18 + TypeScript frontend (Vite)
│   └── src/
│       ├── components/   # UI components
│       ├── hooks/        # React Query hooks
│       ├── services/     # API client
│       └── types/        # TypeScript type definitions
├── MODEL.md              # Data model design and ER diagram
├── DECISIONS.md          # Ambiguity resolutions and PM questions
├── TRADEOFFS.md          # Features deliberately not built
├── SOURCES.md            # Research citations
└── README.md             # This file
```

---

## Evaluation Guidance

### What to evaluate

1. **Data ingestion pipeline** — Upload the sample files from `docs/` using the file upload
   interface. Verify that records are created with correct scope classifications, data quality
   flags, and monthly allocations.

2. **Multi-tenant isolation** — Log in as `analyst@acme.com` and verify you only see Acme
   Corp records. Log in as `analyst@beta.com` and verify you only see Beta Industries records.

3. **Audit trail** — Edit a record's quantity, then view its audit trail. Verify the original
   value, new value, timestamp, and user are recorded. Approve the record, then verify an
   APPROVE event appears in the trail.

4. **Data quality flags** — The sample SAP file includes rows with blank quantity and zero
   price. Verify these appear as ERROR flags. The utility file includes estimated readings —
   verify these appear as WARNING flags.

5. **Audit lock** — Approve a record, then lock it. Verify that editing and re-approval are
   blocked. Log in as an auditor and verify the unlock action is available.

6. **Duplicate detection** — Upload the same SAP file twice. Verify that the second upload
   creates `potential_duplicate` flags on the re-ingested records.

### Sample data files

| File | Location | Description |
|------|----------|-------------|
| SAP fuel procurement | `docs/sap_fuel_procurement.txt` | 10 rows, mixed date formats, blank quantity, zero price |
| Utility electricity | `docs/utility_electricity.csv` | 8 rows, 2 meters, estimated readings, cross-month billing |
| Concur travel | `docs/concur_travel_export.json` | 3 reports, 8 entries, pending approval, via airport, business class |
| Plant lookup | `docs/sap_plant_lookup.csv` | 9 plant codes with location, state, country |

### Design documentation

- `MODEL.md` — Entity-relationship design and data model justifications
- `DECISIONS.md` — Ambiguity resolutions and open questions for product management
- `TRADEOFFS.md` — Features deliberately not built and why
- `SOURCES.md` — Research citations for data formats and calculation methods
