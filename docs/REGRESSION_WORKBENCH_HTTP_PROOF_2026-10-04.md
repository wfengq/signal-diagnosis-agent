# Regression workbench HTTP proof (2026-10-04)

Surface: **HTTP API + packaged static** on `127.0.0.1:8765` via `create_app` lifespan.
This is **not** a browser/DOM GUI recording. computerUse browser proof was unavailable
(monthly spend limit). The UI calls these same routes.

Case ID: `case_270fd72c28954b36af76a366ee592923`

## Steps

| Step | HTTP | Result summary |
|---|---|---|
| capabilities | 200 | `measurement_available=true`, `recommendation_available=false`, `enabled_profile_ids=[]` |
| create_case | 200 | goal `Phase B HTTP proof: compare builds` |
| initial compare | 200 | metric statuses `descriptive_only`, `not_comparable`; `profile_id=null`; recommendation `unavailable` |
| repeat | 200 | 2 comparisons; `link_kind=repeat` |
| repair | 200 | 3 comparisons; `link_kind=repair` |
| report.json | 200 | schema includes case/comparisons/failures/recommendations + measurement_only_notice |
| report.html | 200 | 4033 bytes HTML |
| `/regression` + `/static/regression.js` | 200 | packaged page/JS served |
| `/api/v1/health` | 200 | diagnosis health unchanged (`planner_configured` reported; no Scripted fallback) |

## Claims

- No RealLLM / no product comparison profile.
- Descriptive-only compare path exercised end-to-end over HTTP.
- Browser GUI lifecycle (DOM events, button pending, late-response UI) **not** recorded here.
