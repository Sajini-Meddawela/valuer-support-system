# Verification record and acceptance checklist

## Checks completed for the no-Docker edition (10 September 2026)

| Check | Result |
| --- | --- |
| Python dependency installation in a clean Python 3.12 venv | Passed on Linux |
| TypeScript check and Vite production build | Passed |
| Python source compilation | Passed |
| Domain unittest suite | 10 passed |
| pytest calculation/API/workflow suite | 8 passed; two non-failing dependency/serializer warnings |
| Built frontend served by FastAPI at `/` | Passed through TestClient |
| Health endpoint and denial of `.env`/unknown API paths | Passed through TestClient |
| Real DOCX and LibreOffice PDF export using synthetic input | Passed through API smoke test |
| Review, final approval and archived PDF with actual converter | Passed through API smoke test |
| Template and synthetic populated report page inspection | All 6 source-template pages and 4 populated pages inspected; QR caption and certification grouping corrected |
| Local configuration generation and preservation on rerun | Passed on Linux |
| Confidential reference | Original document and media excluded; only generic report structure used |

## Checks not completed here

Windows `.cmd` scripts were prepared and inspected but could not be executed on this Linux workspace. Run setup and exports on the actual Windows laptop. No live Google Maps request was made because no key was supplied. No report or sample coordinates were sent to Google.

No real GitHub repository was created, pushed or used to run Actions. CI YAML is supplied for you to run after pushing. No public server, systemd service, Nginx/TLS deployment or interactive browser workflow was tested here. The real PDF smoke check used one synthetic land-only report; it does not establish correct layout for every property or target Office/font configuration.

The package is a development MVP. Complete the checklist below before a controlled pilot, using synthetic data until checks pass. Dependency pins are not a security audit or a complete transitive lockfile.

## Automated checks to run

From backend after installing requirements:

```bash
python -m unittest tests.domain_checks -v
python -m pytest -q
```

The pytest suite covers report ownership (including map/photo/export/history endpoints), concurrent revision rejection, XML escaping, map-export gating, photo format validation, required review fields, approval locking, profile changes not altering archived files, and creating revised drafts. Its PDF conversion is mocked only in the lifecycle test; this does not substitute for real converter checks.

From frontend:

```bash
npm ci
npm run build
npm audit
```

Run dependency vulnerability checks for Python as part of release preparation as well. The package includes pinned direct dependencies; it is not an audited dependency set or full transitive Python lockfile.

## Manual acceptance checklist

1. Start with a fresh test database. Register two different accounts.
2. Save different valuer/bank profiles. Confirm one account cannot see another's reports or attachments.
3. Make a land-only report with synthetic values and export a DOCX. Verify no building-description section appears.
4. Make a building report with several floors. Independently recompute the total and confirm rates/areas in the report.
5. Test decimal rates, cents, zero coordinates, long names, `&`/`<` characters and multiline descriptions.
6. Verify acres/roods/perches conversion, explicit depreciation, positive/negative adjustments, rounding and the override reason.
7. Leave optional insurance/forced-sale values blank and verify no invented values appear.
8. Enter each optional value and verify both numeric and word versions and the explanation.
9. Upload landscape and portrait photos. Confirm aspect ratios and captions. Reject non-image files.
10. With authorised Google configuration, preview the map, verify the exact point, zoom and attribution, and test the optional supplied access path.
11. Test missing API key, map-service error and disabled export rights. The app must show an error rather than a fabricated or missing map marked as successful.
12. Export a REAL PDF using LibreOffice. Inspect every page in Word and PDF, including page numbering, maps, image captions, empty sections and signatures.
13. Submit for review. Edit a field; verify it returns to draft.
14. Approve a reviewed report. Verify final files download and that edits/photo changes are blocked.
15. Change your profile and the template. Confirm that final downloads are byte-identical to the archived files.
16. Create a revised copy of the same property. Confirm the old final remains intact.
17. Open the same draft in two tabs. Save both; the stale tab must receive HTTP 409.
18. Stop and restart the Python backend (or hosted service). Verify reports, photos and final archives remain available.
19. Restore a database AND attachment backup into a separate test installation.
20. Have the practising valuer and intended bank review the template, wording, rounding policy and operational workflow.

Only after those pass should you use this as a controlled pilot. Broader deployment also needs the operational and security additions listed in the README.
