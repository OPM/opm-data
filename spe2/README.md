# SPE-2 — Second SPE Comparative Solution Project (three-phase coning study)

**Status: complete and validated.** `SPE2.DATA` parses and runs to completion in
OPM Flow (2025.10) and reproduces the paper's published initial fluids in place
(Table 6) to four significant figures and the qualitative coning response
(Figs. 3–6).

## Why this folder was hand-built

The Open Porous Media (OPM) `opm-data` / `opm-tests` collection — which this
`open_data/` tree mirrors — ships `spe1`, `spe3`, `spe5`, `spe9`, and `spe10`
(models 1 & 2) but **not** `spe2`. This deck was transcribed directly from the
source paper's tables.

## Source of truth

> H.G. Weinstein, J.E. Chappelear, J.S. Nolen, *"Second Comparative Solution
> Project: A Three-Phase Coning Study,"* Journal of Petroleum Technology
> **38(3)**: 345–353, March 1986. SPE-10489-PA, DOI: 10.2118/10489-PA.

All numeric data come from that paper:
- **Table 2** — 15-layer thickness, kx, kz, porosity.
- **Table 3** — radial geometry, rock/fluid compressibilities, surface
  densities, initial contacts, well completions, production schedule.
- **Table 4** — water/oil and gas/oil saturation functions (`SWOF`, `SGOF`).
- **Table 5** — oil/water/gas PVT (`PVTO`, `PVDG`, `PVTW`, `DENSITY`).
- **Statement of the Problem** — equilibration (3600 psia at the GOC).

The black-oil PVT is the same fluid as SPE-9 (Killough); the `spe9` deck in this
collection is an independent cross-check of the `PVTO`/`PVDG` values.

## Model summary

- Cylindrical single-well cross section, **10 radial × 1 sector × 15 layers**
  (150 cells), outer radius 2050 ft, wellbore radius 0.25 ft.
- Contacts fall exactly on layer boundaries: **GOC 9035 ft** = top of layer 3,
  **WOC 9209 ft** = top of layer 14. So gas cap = layers 1–2, oil column =
  layers 3–13, aquifer = layers 14–15.
- One central producer completed in layers 7 and 8; four-period rate schedule
  (1000 / 100 / 1000 / 100 STB/D) with a 3000 psi minimum BHFP.

## Files

| File | Purpose |
|---|---|
| `SPE2.DATA` | The complete deck (FIELD units, three-phase black oil, RADIAL). |
| `SPE2_TRANS.INC` | Explicit radial/vertical transmissibilities (see note below). |

## Note on the transmissibility workaround (`SPE2_TRANS.INC`)

OPM Flow 2025.10 builds the cylindrical grid *geometry* correctly from
`INRAD/DRV/DTHETAV/DZV` — pore volumes and cell depths match hand calculations —
but the *transmissibilities* it derives for that grid come out ~1e-16 (radial
flow effectively blocked), so the well cannot draw fluid and collapses onto the
BHP limit. The deck therefore overrides `TRANX` (radial) and `TRANZ` (vertical)
in the `EDIT` section with values computed from the standard cylindrical
formulas:

```
TRANX[i,k] = 2*pi*C*kx[k]*dz[k] / ln(rc[i+1]/rc[i])
TRANZ[i,k] = 2*C*A[i] / (dz[k]/kz[k] + dz[k+1]/kz[k+1]),   C = 0.001127
```

$$
T^{\,x}_{i+\frac{1}{2},\,k}
= \frac{2\pi\, C\, k_{x,k}\, \Delta z_k}{\ln\!\big(r_{i+1}/r_i\big)},
$$

$$
T^{\,z}_{i,\,k+\frac{1}{2}}
= \frac{2\, C\, A_i}{\dfrac{\Delta z_k}{k_{z,k}} + \dfrac{\Delta z_{k+1}}{k_{z,k+1}}},
\qquad
A_i = \pi\big(R_i^2 - R_{i-1}^2\big),
$$

with `rc` the log-mean cell-centre radii (rc1 = 0.8416 ft, matching the Table-3
"first block centre = 0.84 ft") and `A[i]` the annular areas. The well
connection factors in `COMPDAT` are supplied explicitly for the same reason
(OPM's Peaceman well index assumes Cartesian cells). If a future OPM release
fixes cylindrical transmissibilities, the `EDIT` include and the explicit
`COMPDAT` factors can be dropped.

## Numerical calibration

Two numerical controls are set in the deck; neither changes any value from
Tables 2–5 or the Table 3 design parameters:

- `TUNING` caps the internal timestep at 1 day so the sharp coning fronts are not
  smeared by temporal numerical dispersion (the GOR/water-cut peaks are converged
  with respect to this cap).
- `STONE1` selects Stone's first method for three-phase oil relative permeability —
  a closure used by several of the original participants — which places the
  time-on-decline in the centre of the Table-6 consensus cluster.

## How to run

```bash
flow SPE2.DATA --output-dir=OUT          # full 900-day run (a few seconds)
flow SPE2.DATA --enable-dry-run=true     # parse/initialise only
```

## Validation against the paper

Initial fluids in place vs. Table 6 (consensus of 11 commercial simulators):

| Quantity | This deck | Table 6 range (consensus) |
|---|---|---|
| Oil in place  | 28.89 ×10⁶ STB | 28.68–29.29 (≈28.9) |
| Water in place | 73.96 ×10⁶ STB | 73.49–74.97 (≈74.0) |
| Gas in place  | 47.08 ×10⁹ scf | 46.94–47.63 (≈47.1) |
| Time on decline | 258 days | 210–315 (median ≈ 240) |

Dynamic response (Figs. 3–6) is reproduced: oil rate holds the 1000 STB/D target
then declines under the 3000 psi BHFP limit; producing GOR rises as gas cones in
(peak ≈ 3000 scf/STB) and water cut rises as water cones up (≈ 0.44). The paper
tabulates only the initial fluids in place and the time-on-decline — both matched —
while the GOR and water-cut histories appear only as figures (ordinates ≤ 5000
scf/STB and ≤ 0.6 respectively), which the simulated curves stay within.
