# Template and field map

The supplied clean template uses the report schema in `backend/app/schemas.py`. It is an editable baseline following the reference report's sections, not an exact recreation of that confidential document.

## Input groups

| Prefix | Data |
| --- | --- |
| `valuer` | Name, qualifications, registration, address, telephone, email |
| `bank` | Bank name, branch, recipient and address |
| `assignment` | References, request/inspection/valuation/report dates, purpose, applicant and owner |
| `property` | Address, land/lot/plan identifiers, surveyor, extent, coordinates, descriptions and boundaries |
| `building` | Description, construction, condition, occupancy and repeating floor rows |
| `findings` | Documents, approvals, legal assumptions, deed information, method, evidence and certification |
| `valuation` | Adopted rates, improvements, depreciation, adjustments and final-value decisions |
| `calc` | Server-calculated totals, areas and wording; never accepted as trusted client input |

All optional descriptive fields default to blank, not to a previous property's findings. Complete required fields before approval. The document uses `Not supplied` for blank optional descriptions so missing information is visible.

## Word placeholders

```text
{{ assignment.reference }}
{{ assignment.owner|blank }}
{{ property.plan_date|blank }}
{{ valuation.land_rate_per_perch|money }}
{{ calc.market_value|money }}
{{ calc.market_value_words }}
```

Keep every placeholder intact. Use paragraph controls on their own paragraphs:

```text
{%p if property.kind == "land_building" %}
... building section ...
{%p endif %}
```

For repeating floor tables, put the control on a dedicated table row:

```text
{%tr for floor in building.floors %}
{{ floor.name }} | {{ floor.area_sqft }} | {{ floor.rate_per_sqft|money }}
{%tr endfor %}
```

The `|` above represents separate cells for illustration. Do not paste one pipe-delimited line in place of a real table.

For photographs:

```text
{%p for photo in photos %}
{{ photo.image }}
{{ photo.caption }}
{%p endfor %}
```

`map_image`, `qr_image` and `photo.image` are inserted by the backend. They are not URLs supplied by the browser. The QR encodes the supplied map coordinates. The original map attribution stays in the full image.

`status` marks draft vs approved final. `template_version` includes a template content hash. Header and footer placeholders reuse the same inputs as the main body. Archived final Word and PDF files are not re-rendered after a template change.

## Formatting acceptance

Test a land-only report, a multi-floor building, long names/addresses, multiline findings, special characters, absent optional values, many photographs and a map-enabled report. Review every page of the exported PDF and open the Word file in the actual Office version used by the valuer. Never assume a fixed page count across different input lengths.

Template source is trusted administrator-controlled code. Do not expose arbitrary template uploads without a separate security design. Do not carry confidential sample content, tracked changes, embedded original media or document metadata into a reusable product template.
