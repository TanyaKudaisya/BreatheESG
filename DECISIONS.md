# DECISIONS.md — Ambiguity Resolutions and Open Questions

This document records every ambiguity encountered during implementation, the decision made,
and the reasoning behind it. It also lists open questions for product management where the
right answer depends on business policy rather than engineering judgment.

---

## Resolved Ambiguities

### 1. Unknown Plant Codes (SAP WERKS)

**Ambiguity:** The requirements say the ingestion engine should resolve WERKS codes to
human-readable locations using the Plant Lookup Table. The requirements do not specify what
to do when a WERKS code appears in the SAP file but is not present in the lookup table.

**Decision:** Ingest the record, use the raw WERKS code as the `location` field value, and
create a `WARNING`-severity `DataQualityFlag` of type `unknown_plant` on the record.

**Reasoning:**

- Blocking ingestion on an unknown plant code would cause entire file uploads to fail
  silently if a new plant has been added to SAP but not yet to the lookup table. This is
  a common operational scenario in large enterprises.
- A WARNING flag surfaces the issue to the analyst without preventing ingestion or approval.
  The analyst can correct the location manually before approving.
- Using the WERKS code as a fallback preserves the original identifier so the analyst knows
  which plant to look up.

**Example:** WERKS code `WRK9` not in lookup → `location = "WRK9"`, flag created with
message `"Plant code WRK9 not found in lookup table; using WERKS code as location fallback"`.

---

### 2. Lubricating Oil Handling

**Ambiguity:** Requirement 2.7 says the ingestion engine SHALL "exclude materials containing
lubricating oil from emission calculations." The requirement does not specify whether
"exclude" means (a) do not create a database record at all, or (b) create a record but mark
it as excluded from calculations.

**Decision:** Create the `EmissionRecord` with `scope = None` and `scope_category = None`.
The record is stored in the database but will not appear in any scope-based aggregation or
reporting query because it has no scope assignment.

**Reasoning:**

- Discarding the record entirely would mean there is no audit trail for lubricating oil
  procurement. An auditor reviewing the SAP file would see rows that have no corresponding
  database record, which raises questions about data completeness.
- Storing the record with `scope = None` preserves the raw data and audit trail while
  effectively excluding it from GHG calculations (which filter on `scope IN (1, 2, 3)`).
- The `raw_data` JSONB field still contains the original SAP row, so the full procurement
  picture is available if needed.

**Open question for PM:** See Question 1 below.

---

### 3. Billing Period Allocation Rounding

**Ambiguity:** When a utility billing period is proportionally allocated across calendar
months, the allocation is calculated as `(days_in_month / total_days) * consumption_kwh`.
Floating-point arithmetic means the sum of allocations may not exactly equal the original
consumption due to rounding.

**Decision:** The last month in the billing period receives the remainder:
`last_month_allocation = original_consumption - sum(all_other_months)`.

**Reasoning:**

- This guarantees that `sum(monthly_allocations) == original_consumption` exactly, which
  is a correctness property tested by the property-based test suite.
- The rounding error is always placed in the last month rather than distributed, which
  makes the allocation deterministic and auditable.
- The magnitude of the rounding error is at most a few milliwatt-hours for typical
  consumption values, which is negligible for GHG reporting purposes.

**Example:** 1000 kWh over 31 days spanning Jan 15 – Feb 14:
- January: 17 days → `(17/31) * 1000 = 548.387...` kWh → stored as `548.387097`
- February: 14 days → `1000 - 548.387097 = 451.612903` kWh (remainder assigned here)

---

### 4. Cabin Class Multiplier Application

**Ambiguity:** Requirement 4.6 says "apply a cabin class emission multiplier of 3.0 relative
to ECONOMY class" for BUSINESS class flights. The requirement does not specify whether the
multiplier is applied to the distance or stored as a separate field.

**Decision:** The multiplier is applied to `distance_km` at ingestion time. A BUSINESS class
flight from DEL to LHR (6,700 km) is stored with `distance_km = 20,100` (6,700 × 3.0).
The original cabin class is preserved in the `cabin_class` field.

**Reasoning:**

- The system does not calculate kg CO2e (see TRADEOFFS.md). The `distance_km` field is the
  primary emission-relevant quantity for air travel. Applying the multiplier to distance
  means downstream emission factor calculations can treat all records uniformly:
  `distance_km * emission_factor_per_km`.
- Storing the multiplied value makes the data self-contained — a consumer of the API does
  not need to know the cabin class multiplier to use the distance value correctly.
- The `cabin_class` field is preserved so analysts can verify the multiplier was applied
  correctly and auditors can reconstruct the original distance if needed.

**Open question for PM:** See Question 3 below.

---

### 5. Unknown Airport Codes

**Ambiguity:** Requirement 17.4 says "if an airport code is not found in the lookup table,
create a DataQualityFlag indicating unknown airport." The requirement does not specify
whether ingestion should continue or halt for that record.

**Decision:** Ingestion continues. The record is created with `distance_km = null` and a
`WARNING`-severity `DataQualityFlag` of type `unknown_airport`.

**Reasoning:**

- The expense report data (employee, department, dates, amounts) is still valid and useful
  even if the distance cannot be calculated. Blocking the entire record would discard
  valuable data.
- A WARNING flag (not ERROR) means the analyst can still approve the record after reviewing
  it. If the analyst knows the correct airport code, they can edit the record.
- `distance_km = null` is an explicit signal that the distance is unknown, rather than
  silently storing zero (which would undercount emissions).

**Open question for PM:** See Question 2 below.

---

### 6. Concur `approval_status: PENDING_APPROVAL` Records

**Ambiguity:** Some Concur expense reports have `approval_status: PENDING_APPROVAL`,
meaning the employee's manager has not yet approved the expense. The requirements say to
create a DataQualityFlag but do not specify whether these records should be ingested.

**Decision:** Ingest the record and create a `WARNING`-severity flag of type
`pending_approval`. The record can be approved by the analyst once the Concur approval
is confirmed out-of-band.

**Reasoning:**

- Excluding pending records would mean re-uploading the Concur export after every approval,
  creating operational overhead. It is simpler to ingest everything and let the analyst
  decide.
- The WARNING flag (not ERROR) means the analyst can approve the record if they have
  confirmed the expense was subsequently approved in Concur.

---

### 7. Via-Airport Flight Distance

**Ambiguity:** Requirement 4.9 says to compute distances for both legs of a via-airport
flight separately. The requirement does not specify whether the two legs should be stored
as separate `EmissionRecord` rows or as a single record with the total distance.

**Decision:** One `EmissionRecord` per Concur expense entry. For a flight with `via_airport`,
the `distance_km` field stores the sum of both legs (origin→via + via→destination). The
individual leg distances are not stored separately.

**Reasoning:**

- The Concur expense entry is the atomic unit of data — one entry, one record. Splitting
  a single expense entry into two records would complicate duplicate detection (the natural
  key is `report_id + entry_id`) and approval workflow.
- The total distance is what matters for emission calculations. The via airport is preserved
  in the `via_airport` field for audit purposes.

---

## Open Questions for Product Management

### Question 1: Should lubricating oil records be completely excluded from the database?

**Current behaviour:** Lubricating oil procurement records are stored in the database with
`scope = None`. They appear in the raw data view but are excluded from scope-based reports.

**Alternative:** Do not create a database record for lubricating oil rows at all. The
ingestion summary would report them as "skipped" rather than "ingested."

**Why this matters:** If auditors review the SAP file and count rows, they will see more
rows in the source file than in the database. This could raise questions about data
completeness. On the other hand, storing non-emission procurement data in an emissions
database may be confusing.

**Recommendation:** Keep the current behaviour (store with `scope = None`) unless there is
a specific auditor requirement to exclude non-fuel procurement entirely.

---

### Question 2: Should unknown airport codes block ingestion of the entire travel record?

**Current behaviour:** Records with unknown airport codes are ingested with `distance_km = null`
and a WARNING flag. The analyst can approve them.

**Alternative:** Treat unknown airport codes as an ERROR flag, blocking approval until the
airport code is corrected or the distance is manually entered.

**Why this matters:** A record approved with `distance_km = null` will contribute zero
distance to any emission calculation, silently undercounting travel emissions. If the
analyst does not notice the WARNING flag, this could go undetected.

**Recommendation:** Consider upgrading unknown airport to an ERROR flag if the system will
be used for regulatory reporting where completeness is required.

---

### Question 3: Should the cabin class multiplier be stored separately rather than baked into `distance_km`?

**Current behaviour:** BUSINESS class distance is stored as `distance_km * 3.0`. The
original unmodified distance is not stored.

**Alternative:** Store the raw great-circle distance in `distance_km` and store the
multiplier in a separate `cabin_class_multiplier` field. Downstream calculations apply
the multiplier when computing emissions.

**Why this matters:** If the GHG Protocol updates the BUSINESS class multiplier (currently
3.0 per DEFRA guidance), the stored `distance_km` values would need to be recalculated.
With the alternative approach, only the multiplier configuration would need updating.

**Recommendation:** If the system will be used for multi-year reporting where multipliers
may change, store the raw distance and multiplier separately. For the current prototype
scope, baking the multiplier into `distance_km` is simpler.

---

### Question 4: Should estimated utility readings be blocked from approval?

**Current behaviour:** `reading_type = ESTIMATED` creates a WARNING flag, which does not
block approval. Analysts can approve estimated readings.

**Alternative:** Treat estimated readings as ERROR flags, requiring the analyst to either
obtain an actual reading or manually override the value before approving.

**Why this matters:** GHG Protocol guidance recommends using actual meter readings where
available. Approving estimated readings without review could introduce inaccuracy into
reported emissions.

**Recommendation:** Discuss with the sustainability team whether estimated readings are
acceptable for their reporting methodology, or whether they should always be replaced with
actuals before submission.
