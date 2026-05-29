# Sample Data — Breathe ESG Prototype

Four files, three sources. Here's what each is and why it looks the way it does.

---

## 1. `sap_fuel_procurement.txt` — SAP MM flat file export

**Format chosen:** Tab-separated flat file exported via SE16 (table browser) on EKPO + MSEG join,
the most common way sustainability teams actually receive SAP data — not IDoc (that's
system-to-system middleware) and not OData (that requires API setup most clients haven't done).
When someone at a plant says "I'll pull the fuel PO data from SAP", they mean SE16 → List →
Export → Local File → Spreadsheet/Text. This is that file.

**Columns map to real SAP EKPO/MSEG fields:**
- `EBELN` = Purchase Order number, `EBELP` = line item
- `BEDAT` = document date — deliberately uses four different date formats across rows
  (`YYYYMMDD`, `DD.MM.YYYY`, `YYYY-MM-DD`, `DD/MM/YYYY`) because SAP date display
  depends on user locale settings, and real exports from a multi-plant enterprise will have
  this inconsistency when different users exported different batches.
- `WERKS` = Plant code (opaque without the lookup table — see `sap_plant_lookup.csv`)
- `MEINS` = Unit of measure — `L`, `LTR`, `M3`, `KG` all appear for the same material class.
  This is intentional: different plants configure UoM differently, and the same physical
  material (diesel) appears in litres from one plant and no unit from another.
- `MENGE` = Quantity — one row has a blank quantity (row for PNG on 2024-01-25), simulating
  a goods receipt not yet posted.
- `NETPR` = Net price — two rows show 0.00 price (Furnace Oil FO-180 in KG), simulating
  a price update that hasn't been maintained in the info record yet.
- `TXZ01` = short text — mix of English and abbreviations; real SAP short texts are messy.
- `BUKRS` = Company code; `KOSTL` = Cost centre — needed for multi-entity attribution.

**Materials included (and why each matters for ESG):**
- Diesel HSD — Scope 1, mobile & stationary combustion
- Petrol 91 RON — Scope 1, fleet
- Piped Natural Gas — Scope 1, stationary combustion
- Furnace Oil FO-180 — Scope 1, high-emission industrial fuel
- LPG — Scope 1, cooking/heating
- Lubricating Oil — not a direct emission source; included to test the ingestion pipeline's
  ability to filter non-fuel procurement
- Bituminous Coal — Scope 1, power generation

**What the pipeline must handle:**
- Normalise all date formats to ISO 8601
- Resolve WERKS → human-readable location via lookup
- Normalise units: L and LTR → litres; M3 → cubic metres; KG stays KG
- Skip or flag rows with blank quantity or zero price
- Classify materials by emission category using MATNR / TXZ01 matching

---

## 2. `utility_electricity.csv` — Utility portal CSV export

**Format chosen:** CSV portal download, the near-universal self-serve mechanism for commercial
accounts at Indian discoms (MSEDCL, TNEB, DGVCL, BESCOM). These portals let you select a
date range and download bill history as CSV. PDFs are the other option, but CSV is available
on all four major portals and is far more structured. API access (e.g. via Green Button / ESPI)
exists in the US but is not widely available from Indian utilities as of 2024.

**Key realism baked in:**
- Billing periods do **not** align with calendar months. MSEDCL bills on a ~30-day rolling cycle
  starting from meter read date. Periods like Jan 4 – Feb 3 are normal. This breaks naive
  "just group by month" logic.
- Two meters on the same account (`MTR-PNE-001`, `MTR-PNE-002`) at the same address —
  common for large industrial premises with separate HT and LT connections.
- `ESTIMATED` reading type (TNEB CHN-002 in Jan, MSEDCL PNE-001 in March) — utilities
  estimate when the meter reader can't access the premises. Estimated reads need to be
  flagged differently for ESG reporting because they're not actuals.
- `demand_kw` is 0 for estimated reads — the demand figure is only from an actual reading.
- `tod_peak_kwh` and `tod_offpeak_kwh` — Time-of-Day metering splits consumption into
  peak/off-peak. Relevant for some emission factor methodologies (location-based vs
  time-adjusted). These are blank (0) for estimated reads.
- `power_factor_penalty_inr` appears for some meters — a financial charge, not a consumption
  figure, included to test that the pipeline doesn't accidentally sum it into kWh.
- Different tariff codes (`HT-1A`, `HT-II`, `HT-General`, `HT-2B`, `LT-IV`) across discoms —
  the pipeline must not assume a single rate.
- `fuel_adjustment_inr` — a variable surcharge based on the utility's fuel cost; relevant
  context but not part of consumption.

**What the pipeline must handle:**
- Primary field: `consumption_kwh` — this is what feeds into emission calculations
- Normalise billing periods to a reporting calendar (split or attribute to months)
- Flag estimated reads for analyst review
- Deduplicate if the same bill appears twice (re-exports happen)
- `total_amount_inr` is financial context, not an emission input

---

## 3. `concur_travel_export.json` — Concur Expense API export

**Format chosen:** JSON response shape from the Concur Expense v3 API
(`GET /api/v3.0/expense/reports` + entries). In practice, Navan and TravelPerk have similar
REST structures. The v3 API is what most enterprise integrations actually use; v4 exists but
v3 is more widely deployed. A sustainability team typically receives this via a scheduled
export or an IT-maintained connector, not direct API access.

**Expense types and their Scope 3 category:**
- `AIRFARE` → Scope 3, Category 6 (Business Travel - Air)
- `HOTEL` → Scope 3, Category 6 (Business Travel - Accommodation)
- `GROUND_TRANSPORT_TAXI` → Scope 3, Category 6 (Business Travel - Road)
- `GROUND_TRANSPORT_RENTAL_CAR` → Scope 3, Category 6 (Business Travel - Road, private car)
- `GROUND_TRANSPORT_METRO` / `GROUND_TRANSPORT_RAIL` → Scope 3, Category 6 (Rail)

**Key realism baked in:**
- `distance_km: null` on all flights — Concur stores fare, routing, and cabin class but
  **not distance**. Distance must be calculated from airport codes (great-circle or
  actual route). The pipeline needs an airport-code-to-coordinates lookup or a routing API.
- One report has `approval_status: PENDING_APPROVAL` (RPT-2024-0201) — data should be
  ingested but flagged; analysts must decide whether to include unapproved reports.
- Cabin class varies: ECONOMY vs BUSINESS — emission factors differ significantly
  (DEFRA radiative forcing multiplier applies to flights; business class factor is ~3x economy
  per GHG Protocol guidance).
- International vs domestic flights in the same dataset (DEL→LHR alongside BLR→BOM) —
  emission factors and radiative forcing multipliers differ.
- `via_airport` on one flight (RPR→BLR via HYD) — a connecting itinerary booked as one
  expense line. The pipeline must decide: treat as one leg or split at HYD.
- Ground transport without receipts (`receipt_attached: false`) — present in real data;
  amounts are self-reported and may need analyst flagging.
- `GROUND_TRANSPORT_RENTAL_CAR` has `fuel_type: PETROL` — emission factor differs from
  a diesel rental or an EV.
- Hotel nights in different countries (IN, SG, GB) — emission factors for accommodation
  vary by country (grid emission intensity affects hotel stays).
- MRT entry has no `distance_km` — public transit distance is often unavailable.

**What the pipeline must handle:**
- Flatten nested structure (report → entries)
- Calculate flight distances from `origin_airport` / `destination_airport` using a
  great-circle distance function or lookup table
- Apply cabin-class multipliers for flights
- Route hotel emission factors by country
- Handle pending-approval records (ingest but flag)
- Deduplicate entries if the same report is re-exported

---

## 4. `sap_plant_lookup.csv` — Plant master reference

A lookup table needed to decode SAP's `WERKS` codes into meaningful locations.
In a real SAP deployment this lives in table T001W. Without it, `WRK1` through `WRK9`
are meaningless strings. The pipeline joins on WERKS to get state/country for
grid emission factor lookups.
