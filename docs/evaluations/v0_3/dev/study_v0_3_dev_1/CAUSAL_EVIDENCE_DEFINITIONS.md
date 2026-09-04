# V0.3 Causal Evidence Definitions (semantic freeze)

## Clipping supported_fault

Requires **all** of:

1. Same-run Evidence `clipping_mechanism=true`
2. Same-run **substantial** clipping rule FAIL citing one of:
   - `rule_clipping_ratio_acceptable` (FAIL) — clipping_ratio above the demo 1% profile threshold
   - `rule_flat_top_absent` (FAIL) — reliable flat-top detection under the profile

`clipping_mechanism=true` alone is **not** sufficient. Sparse isolated full-scale samples (e.g. low_snr `29fb`) that leave ratio PASS and flat-top PASS must not become causal clipping.

Invalid harmonic measurement (`valid=false`) does **not** automatically negate the above sufficient clipping Evidence set.

## Harmonic_distortion supported_fault

Requires same-run Evidence:

- `series_kind=even_order_present` (operational spectral structure)
- plus THD rule FAIL for the affirmative operational path under this contract

### series_kind semantics

| Label | Meaning |
|-------|---------|
| `even_order_present` | One or more even-order components exceed the presence floor |
| `native_odd_series` | Only odd-order components present |
| `multi_partial` | H2 relative amplitude ≥ 1.0 (strong second partial) |
| `not_applicable` | Harmonic analysis invalid / not usable |

`even_order_present` is **operational evidence inferred from spectrum**, not injection provenance. Natural even-order content can produce the same label. It must not be treated as ground-truth causal injection.

Historical alias: `injection_mechanism` (renamed in this freeze).
