# TRADEOFFS.md — Features Deliberately Not Built

This document explains what was intentionally left out of the prototype, why, and what
would be needed to add each feature in a production system.

---

## Scope Statement

The system is scoped to **data ingestion, normalization, validation, and analyst review**.
It is explicitly not a GHG reporting platform, a real-time integration platform, or a
production-hardened SaaS product. The goal is to demonstrate data quality discipline and
audit trail integrity, not to build a complete ESG management suite.

---

## Features Not Built

### 1. Emission Factor Calculations (kg CO2e)

**What was not built:** The system does not calculate greenhouse gas emissions in kg CO2e.
There are no emission factor lookups, no unit-to-CO2e conversions, and no total emissions
aggregations.

**Why:** Emission factor calculations require authoritative, jurisdiction-specific factor
databases (DEFRA, EPA, IEA, CEA for India) that change annually. Implementing this
correctly would require:

- A versioned emission factor database with effective date ranges
- Country/region-specific grid emission factors for electricity (Scope 2)
- Fuel-specific combustion factors for Scope 1
- Radiative forcing multipliers for aviation (Scope 3)
- A calculation audit trail showing which factor version was used

Building this correctly is a significant project in its own right. For this prototype, the
focus is on getting clean, validated activity data into the system — the prerequisite for
any emission calculation. The `distance_km`, `consumption_kwh`, and `normalized_quantity`
fields are the inputs that an emission calculation layer would consume.

**What would be needed:** A `EmissionFactor` model with `fuel_type`, `unit`, `kg_co2e_per_unit`,
`source`, `effective_from`, `effective_to` fields, plus a calculation service that joins
records to factors and stores the result with the factor version used.

---

### 2. Reporting and Aggregation Endpoints

**What was not built:** There are no API endpoints for aggregated reports such as:
- Total Scope 1/2/3 emissions by month
- Emissions by location or department
- Year-over-year comparisons
- GHG Protocol disclosure tables

**Why:** Reporting requires emission calculations (see above), which are out of scope.
Additionally, reporting requirements vary significantly by client (different scopes,
different boundaries, different methodologies), making a generic reporting layer difficult
to design without real client requirements.

**What would be needed:** Aggregation views or materialized views on the `EmissionRecord`
table, plus a reporting API that accepts filters (date range, scope, source system, tenant)
and returns aggregated totals. This would be straightforward to add once emission factors
are implemented.

---

### 3. Real-Time Concur API Integration

**What was not built:** The system accepts Concur data as a JSON file upload rather than
connecting directly to the Concur Expense v3 API. There is no OAuth flow, no scheduled
polling, and no webhook receiver.

**Why:** Real Concur API integration requires:
- OAuth 2.0 client credentials registered with SAP Concur
- A scheduled job or webhook to pull new expense reports
- Handling of Concur's pagination (cursor-based for v3)
- Incremental sync logic to avoid re-ingesting already-processed reports

This is an integration engineering task that depends on the client having a Concur
subscription and IT access to register an API client. For a prototype demonstrating
ingestion logic, a JSON file upload that matches the Concur v3 response schema achieves
the same result.

**What would be needed:** A Celery task (or similar) that calls
`GET /api/v3.0/expense/reports` with OAuth bearer token, handles pagination, and passes
each report batch to the existing `ingest_travel_json()` method. The ingestion logic itself
would not change.

---

### 4. Email Notifications

**What was not built:** There are no email notifications for:
- Ingestion completion summaries
- Records flagged for review
- Approval/rejection notifications to record owners
- Audit lock notifications

**Why:** Email delivery requires an SMTP provider (SendGrid, SES, Postmark), email
templates, and user preference management. These are operational concerns that add
complexity without demonstrating the core data quality and audit trail capabilities.

**What would be needed:** Django's built-in email framework with a transactional email
provider, plus signal handlers on `EmissionRecord` state changes to trigger notifications.

---

### 5. Frontend Polish

**What was not built to production standard:**

- **Responsive design:** The dashboard is designed for desktop use. Mobile layouts are
  not implemented.
- **Accessibility:** Basic semantic HTML is used but WCAG 2.1 AA compliance has not been
  audited with assistive technologies.
- **Internationalization:** All UI text is in English. No i18n framework is integrated.
- **Error boundaries:** React error boundaries are not implemented; unhandled errors will
  crash the component tree.
- **Loading skeletons:** Data loading states use simple spinners rather than skeleton
  screens.
- **Keyboard navigation:** Bulk selection and approval workflows are not fully keyboard-
  accessible.

**Why:** The frontend is functional and demonstrates all required workflows. Production
polish requires UX design review, accessibility audit, and cross-browser testing — all of
which are out of scope for a technical prototype.

---

### 6. Rate Limiting

**What was not built:** The travel ingestion endpoint (`POST /api/v1/ingest/travel/`) does
not enforce the 100 requests/minute per tenant rate limit specified in Requirement 16.5.

**Why:** Rate limiting in Django requires either a third-party package (django-ratelimit,
DRF throttling) or a Redis-backed counter. DRF's built-in throttling was not configured
because the prototype does not have a Redis instance in its deployment stack.

**What would be needed:** Add `DEFAULT_THROTTLE_CLASSES` and `DEFAULT_THROTTLE_RATES` to
DRF settings, implement a `TenantScopedThrottle` class that uses `tenant_id` as the cache
key, and add Redis to the deployment.

---

### 7. Scope Classification Manual Override Persistence

**What was not built:** The frontend includes a scope override UI component, but the
backend does not persist the override justification note as a structured field. The
`scope` and `scope_category` fields can be edited via the PATCH endpoint, but there is
no dedicated `scope_override_reason` field or audit event type for scope overrides.

**Why:** The approval workflow audit trail captures all field changes including scope
changes via the generic UPDATE event. A dedicated override reason field would improve
clarity but was deprioritized in favour of completing the core ingestion pipeline.

**What would be needed:** Add `scope_override_reason` and `scope_overridden_by_user_id`
fields to `EmissionRecord`, and add a `SCOPE_OVERRIDE` event type to `AuditEvent`.

---

### 8. Billing Period Allocation Manual Override

**What was not built:** Requirement 20.5 specifies that analysts should be able to manually
override the proportional billing period allocation. The backend stores allocations in the
`MonthlyAllocation` table and the frontend displays them, but the manual override UI is
not fully implemented.

**Why:** The proportional allocation by days is correct for the vast majority of cases.
Manual overrides are an edge case that requires a custom allocation editor UI, validation
that overrides sum to 100%, and an audit trail for the override. This was deprioritized
in favour of completing the core ingestion and approval workflows.

---

## Technical Debt

| Item | Impact | Effort to Fix |
|------|--------|---------------|
| No PostgreSQL Row-Level Security | Defence-in-depth gap; application-level isolation only | Medium |
| No Redis / rate limiting | Requirement 16.5 not met | Low |
| No emission factor calculations | Core ESG value not delivered | High |
| Frontend not WCAG compliant | Accessibility gap | Medium |
| No real Concur OAuth integration | Simulated only | Medium |
| Scope override reason not persisted | Audit trail gap for manual overrides | Low |
| Billing period manual override not implemented | Requirement 20.5 not met | Low |
