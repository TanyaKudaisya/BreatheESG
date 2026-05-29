# SOURCES.md — Research and Reference Sources

This document cites the sources used to design the data formats, field names, calculation
methods, and classification rules implemented in the Breathe ESG Data Ingestion System.

---

## 1. SAP Export Format

**Source:** SAP SE16 table browser export documentation and SAP EKPO/MSEG table field
reference.

**Relevant fields and their SAP origins:**

| Field in system | SAP table | SAP field | Description |
|-----------------|-----------|-----------|-------------|
| `ebeln` | EKPO | EBELN | Purchase Order number |
| `ebelp` | EKPO | EBELP | Purchase Order line item |
| `bedat` | EKPO | BEDAT | Document date |
| `werks` | EKPO | WERKS | Plant code |
| `menge` / `original_quantity` | EKPO | MENGE | Order quantity |
| `meins` / `original_unit` | EKPO | MEINS | Unit of measure |
| `netpr` | EKPO | NETPR | Net price |
| `txz01` / `material_description` | EKPO | TXZ01 | Short text |
| `matnr` | EKPO | MATNR | Material number |
| `waers` / `currency` | EKPO | WAERS | Currency code |

**Format rationale:** Tab-separated flat file exported via SE16 (table browser) is the
most common mechanism for sustainability teams to extract procurement data from SAP. The
alternative export paths (IDoc, OData/BAPIs) require IT middleware configuration that most
clients have not set up. When a plant controller says "I'll pull the fuel PO data from SAP,"
they mean SE16 → List → Export → Local File → Spreadsheet/Text.

**Date format variation:** SAP date display depends on the user's locale settings
(`SU3 → Defaults → Date format`). A multi-plant enterprise with users in different regions
will produce exports with mixed date formats (`YYYYMMDD`, `DD.MM.YYYY`, `DD/MM/YYYY`,
`YYYY-MM-DD`) when different users export different batches. The normalization service
handles all four formats.

**Reference:** SAP Help Portal — EKPO table documentation:
https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE

---

## 2. Utility Bill CSV Format (Indian Electricity Discoms)

**Sources:** Portal download interfaces for the four major Indian electricity distribution
companies (discoms) serving commercial and industrial customers:

- **MSEDCL** (Maharashtra State Electricity Distribution Co. Ltd.) — serves Maharashtra
  including Mumbai, Pune, Nagpur. Portal: https://www.mahadiscom.in
- **TNEB / TANGEDCO** (Tamil Nadu Generation and Distribution Corporation) — serves Tamil
  Nadu including Chennai. Portal: https://www.tnebnet.org
- **BESCOM** (Bangalore Electricity Supply Company) — serves Bengaluru and surrounding
  districts. Portal: https://bescom.karnataka.gov.in
- **DGVCL** (Dakshin Gujarat Vij Company Ltd.) — serves southern Gujarat. Portal:
  https://www.dgvcl.com

**Key format characteristics observed:**

- Billing periods do not align with calendar months. MSEDCL bills on a rolling ~30-day
  cycle from the meter read date. Periods like "4 January – 3 February" are standard.
- Large industrial premises commonly have multiple meters on the same account number
  (separate HT and LT connections).
- `reading_type` values: `ACTUAL` (meter reader visited) and `ESTIMATED` (meter reader
  could not access premises; utility estimates based on prior consumption).
- `demand_kw` is populated only for actual readings; estimated reads show 0.
- `power_factor_penalty_inr` is a financial charge for poor power factor, not a consumption
  figure. It must not be summed into kWh totals.
- `fuel_adjustment_inr` is a variable surcharge based on the utility's fuel procurement
  cost; it is financial context, not an emission input.
- Tariff codes (`HT-1A`, `HT-II`, `HT-General`, `HT-2B`, `LT-IV`) vary by discom and
  connection type.

**Note:** API access equivalent to the US Green Button / ESPI standard is not widely
available from Indian utilities as of 2024. CSV portal download is the primary structured
data access mechanism for commercial accounts.

---

## 3. Concur Expense API Schema

**Source:** SAP Concur Expense v3 API documentation.

**Reference:** https://developer.concur.com/api-reference/expense/expense-report/v3.reports.html

**Key schema elements used:**

```json
{
  "expense_reports": [
    {
      "report_id": "RPT-2024-0101",
      "approval_status": "APPROVED",
      "entries": [
        {
          "entry_id": "ENT-001",
          "expense_type": "AIRFARE",
          "employee_id": "EMP-001",
          "origin_airport": "DEL",
          "destination_airport": "LHR",
          "cabin_class": "BUSINESS",
          "receipt_attached": true
        }
      ]
    }
  ]
}
```

**Version choice:** The v3 API is used rather than v4 because v3 is more widely deployed
in enterprise integrations as of 2024. The v4 API exists but requires newer OAuth 2.0
flows that many enterprise IT departments have not yet configured.

**Expense type mapping to Scope 3 Category 6:**

| Concur `expense_type` | GHG Protocol Category |
|-----------------------|----------------------|
| `AIRFARE` | Scope 3, Category 6 — Business Travel (Air) |
| `HOTEL` | Scope 3, Category 6 — Business Travel (Accommodation) |
| `GROUND_TRANSPORT_TAXI` | Scope 3, Category 6 — Business Travel (Road) |
| `GROUND_TRANSPORT_RENTAL_CAR` | Scope 3, Category 6 — Business Travel (Road) |
| `GROUND_TRANSPORT_METRO` | Scope 3, Category 6 — Business Travel (Rail/Transit) |
| `GROUND_TRANSPORT_RAIL` | Scope 3, Category 6 — Business Travel (Rail) |

---

## 4. GHG Protocol — Scope Definitions

**Source:** World Resources Institute & World Business Council for Sustainable Development.
*The Greenhouse Gas Protocol: A Corporate Accounting and Reporting Standard* (Revised Edition).

**Reference:** https://ghgprotocol.org/corporate-standard

**Scope definitions applied:**

- **Scope 1 — Direct emissions:** Combustion of fuels owned or controlled by the reporting
  company. Applied to SAP procurement records for diesel, petrol, PNG (piped natural gas),
  furnace oil, LPG, and coal.

- **Scope 2 — Indirect emissions from purchased energy:** Electricity purchased from the
  grid. Applied to all utility electricity records.

- **Scope 3 — Other indirect emissions, Category 6 — Business Travel:** Emissions from
  employee travel in vehicles not owned or controlled by the company. Applied to all Concur
  travel records.

**Cabin class multiplier:** The 3.0× multiplier for BUSINESS class relative to ECONOMY
class is based on DEFRA (UK Department for Environment, Food & Rural Affairs) greenhouse
gas conversion factors for company reporting, which apply a radiative forcing index (RFI)
and seat-area-based class weighting. The GHG Protocol Technical Guidance for Calculating
Scope 3 Emissions (v1.0) references DEFRA factors for aviation.

**Reference:** DEFRA Greenhouse Gas Conversion Factors:
https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting

---

## 5. OpenFlights Airport Database

**Source:** OpenFlights.org airport coordinate database.

**Reference:** https://openflights.org/data.html

**Dataset:** `airports.dat` — a CSV file containing IATA airport codes, airport names,
city, country, latitude, and longitude for approximately 14,000 airports worldwide.

**Fields used:**

| OpenFlights field | Usage |
|-------------------|-------|
| IATA code (3-letter) | Lookup key for origin/destination/via airport codes |
| Latitude (decimal degrees) | Haversine formula input |
| Longitude (decimal degrees) | Haversine formula input |

**License:** The OpenFlights airport database is made available under the Open Database
License (ODbL). Attribution is required for derived works.

---

## 6. Haversine Formula for Great-Circle Distance

**Source:** Standard spherical trigonometry. The formula is named after the haversine
function and is widely documented in navigation and geodesy literature.

**Implementation reference:** Movable Type Scripts — Calculate distance, bearing and more
between Latitude/Longitude points:
https://www.movable-type.co.uk/scripts/latlong.html

**Formula:**

```
a = sin²(Δlat/2) + cos(lat₁) × cos(lat₂) × sin²(Δlon/2)
c = 2 × atan2(√a, √(1−a))
distance = R × c
```

Where:
- `R` = Earth's mean radius = 6,371 km (IUGG value)
- `Δlat` = lat₂ − lat₁ (in radians)
- `Δlon` = lon₂ − lon₁ (in radians)

**Accuracy note:** The Haversine formula assumes a spherical Earth. The actual Earth is
an oblate spheroid; the Vincenty formula gives more accurate results for long-distance
calculations (error < 0.5%). For GHG reporting purposes, the Haversine approximation
(error < 0.3% for most routes) is within acceptable tolerance. The GHG Protocol does not
specify a required distance calculation method.

**Multi-leg flights:** For flights with a via airport, the total distance is calculated
as the sum of two Haversine calculations: origin→via and via→destination. This matches
the approach recommended in DEFRA's guidance for connecting itineraries.

---

## 7. SAP Plant Lookup Table

**Source:** SAP table T001W (Plant/Branch) — the standard SAP master data table mapping
plant codes (WERKS) to plant names, addresses, and country codes.

**Reference:** SAP Help Portal — T001W table:
https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE

In a real deployment, the plant lookup table would be exported from T001W via SE16 and
maintained as a reference file. The sample `sap_plant_lookup.csv` in this repository
represents a simplified version of a T001W export with columns: `WERKS`, `NAME1`
(plant name), `ORT01` (city/location), `REGIO` (state/region), `LAND1` (country code).
