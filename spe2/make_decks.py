r"""
Generate the Cartesian single-well variants of the SPE-2 coning benchmark.

``python ./make_decks.py [variant ...]`` writes the decks of :data:`VARIANTS`
(all of them when none is named) next to this script; edit this file, not the ``.DATA``
files. ``tests/test_spe2_decks.py`` checks that every deck on disk is the generator's output. The parent benchmark (``data/spe2/SPE2.DATA``)
is an axisymmetric radial cross section of :math:`N_r \times N_z = 10 \times 15` blocks with a
producer on the inner boundary. The variants re-express the same reservoir — the fifteen
Table-2 layers, the Table-3 completion, every fluid table and the contacts — on a Cartesian
mesh centred on the well, and replace the four-period coning schedule by one oil-rate
target held to the end of the run.

Grids
-----

**Graded** (``uniform``, ``anis``). The Table-3 radial block boundaries
:math:`R_0 = r_w = 0.25` ft, :math:`R_1, \dots, R_{10} = 2050` ft are mirrored about the well
axis in both horizontal directions,

.. math::

    \mathcal{X} = \{-R_{10},\dots,-R_1,-R_0\}\ \cup\ \{+R_0,+R_1,\dots,+R_{10}\},
    \qquad
    \Delta x_i =
    \begin{cases}
        2 r_w, & i = i_w,\\
        R_m - R_{m-1}, & m = |i - i_w| \ge 1,
    \end{cases}

so the mesh spans 4100 ft, logarithmically graded away from the well, in
:math:`21 \times 21 \times 15` blocks with the well in column :math:`(11, 11)`.

**Equispaced** (``equispaced``). The same 4100 ft square in :math:`25 \times 25` columns of
164 ft, the well in column :math:`(13, 13)`.

Layer properties
----------------

Layer thicknesses :math:`\Delta z_k`, horizontal permeability :math:`k_{x,k}`, vertical
permeability :math:`k_{z,k} = 0.1\,k_{x,k}` and reference porosity :math:`\phi_k` are the
Table-2 values; the parent's ``COPY PERMX PERMY`` keeps the plan isotropic,
:math:`k_y = k_x`. The ``anis`` deck replaces the layer-constant porosity by one frozen
realisation,

.. math::

    \phi_{ijk} = \max\!\left(\phi_{\min},\ \tilde{\phi}_{ijk}\right),
    \qquad
    \tilde{\phi}_{ijk} \sim \mathcal{N}\!\left(\phi_k,\ (0.1\,\phi_k)^2\right),
    \qquad
    \phi_{\min} = 0.05,

drawn once with a fixed seed and written out as literal numbers.

Well and schedule
-----------------

The producer is completed in layers 7 and 8 with a 0.5 ft wellbore and zero skin and holds
an oil-rate target :math:`q_o` with a minimum bottom-hole pressure :math:`p_{bh,\min}` for
the whole run. On the graded grid the well cell is the wellbore footprint, Peaceman's
equivalent radius :math:`r_o = 0.198\,\Delta x` falls inside :math:`r_w` and the connection
factor is stated explicitly with the parent's cylindrical form; on the equispaced grid
:math:`r_o = 32.5` ft and the simulator computes the factor from the cell. Report times
partition the first day geometrically (100 steps of ratio ``TRANSIENT_RATIO``, the first
:math:`6.7 \times 10^{-5}` d), then step 0.5 d to day 10, 2 d to day 100 and 5 d to the end.

where:

- :math:`r_w`: the wellbore radius, 0.25 ft (Table 3).
- :math:`R_m`: the :math:`m`-th Table-3 radial block boundary (ft); :math:`i_w` the well column.
- :math:`\Delta z_k, k_{x,k}, k_{z,k}, \phi_k`: Table-2 thickness (ft), horizontal and vertical permeability (md) and reference porosity of layer :math:`k`.
- :math:`\phi_{ijk}`: the cell porosity written to ``PORO``; :math:`\phi_{\min}` its floor.
- :math:`q_o, p_{bh,\min}`: the variant's oil-rate target (STB/D) and BHP limit (psia).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

# --- Table 3 (Weinstein et al. 1986): radial block boundaries, ft ----------------------------
RADIAL_BOUNDARIES = [
    0.25, 2.00, 4.32, 9.33, 20.17, 43.56, 94.11, 203.32, 439.24, 948.92, 2050.00
]
R_W = RADIAL_BOUNDARIES[0]
R_OUT = RADIAL_BOUNDARIES[-1]

# --- Table 2: per-layer thickness (ft), kx (md), kz (md), porosity (-) -----------------------
LAYER_DZ = [20, 15, 26, 15, 16, 14, 8, 8, 18, 12, 19, 18, 20, 50, 100]
LAYER_KX = [35.0, 47.5, 148.0, 202.0, 90.0, 418.5, 775.0, 60.0, 682.0,
            472.0, 125.0, 300.0, 137.5, 191.0, 350.0]
LAYER_KZ = [0.1 * k for k in LAYER_KX]
LAYER_PORO = [0.087, 0.097, 0.111, 0.160, 0.130, 0.170, 0.170, 0.080, 0.140,
              0.130, 0.120, 0.105, 0.120, 0.116, 0.157]

NZ = len(LAYER_DZ)
N_RING = len(RADIAL_BOUNDARIES) - 1          # 10 graded rings per side
PERF_LAYERS = (7, 8)                         # Table 3 completion layers

# Table 3 well data: permeability-thickness (md-ft) of each completed layer.
WELL_KH = {7: 6200.0, 8: 480.0}
# Log-mean centre radius of the parent model's innermost shell (Table 3: 0.84 ft).
R1_LOGMEAN = 0.8416
DARCY_FIELD_C = 0.001127

POROSITY_CV = 0.10
POROSITY_FLOOR = 0.05
POROSITY_SEED = 20260901

EQUISPACED_N = 25                            # columns per side of the equispaced grid
EQUISPACED_DX = 164.0                        # ft; 25 * 164 = 4100 ft
# Geometric partition of the first day into 100 report steps (first step 6.7e-5 d).
TRANSIENT_STEPS = 100
TRANSIENT_RATIO = 1.0722672


@dataclass(frozen=True)
class Variant:
    """One deck: its folder and file, grid, porosity, rate target and BHP limit."""

    folder: str
    filename: str
    grid: str                 # "graded" | "equispaced"
    porosity: str             # "uniform" | "heterogeneous"
    oil_rate: float           # STB/D
    min_bhp: float            # psia
    total_days: float = 900.0
    label: str = ""


VARIANTS = {
    "uniform": Variant("uniform", "SPE-2-cartesian.DATA", "graded", "uniform", 1000.0, 100.0,
                       label="UNIFORM POROSITY"),
    "anis": Variant("anis", "SPE-2-cartesian-anis.DATA", "graded", "heterogeneous", 1000.0, 100.0,
                    label="HETEROGENEOUS POROSITY"),
    "equispaced": Variant("equispaced", "SPE-2-cartesian-equi.DATA", "equispaced", "uniform",
                          1500.0, 100.0, label="EQUISPACED GRID"),
    # ten years at a target the well can hold for about two: a constant-rate transient, then
    # a pressure-limited decline (radius of investigation and decline-curve analysis)
    "decline": Variant("decline", "SPE-2-cartesian-decline.DATA", "graded", "uniform",
                       1000.0, 1500.0, total_days=3660.0, label="RATE DECLINE"),
}


def cell_widths(grid: str = "graded") -> list[float]:
    r"""
    The column widths :math:`\Delta x_i` (ft), :math:`-x` edge to :math:`+x` edge: on the
    graded grid the reversed Table-3 ring widths, the central well cell of width
    :math:`2 r_w`, then the ring widths; on the equispaced grid ``EQUISPACED_N`` columns of
    ``EQUISPACED_DX``. The same widths serve the :math:`y` direction.
    """
    if grid == "equispaced":
        return [EQUISPACED_DX] * EQUISPACED_N
    ring = [RADIAL_BOUNDARIES[m + 1] - RADIAL_BOUNDARIES[m] for m in range(N_RING)]
    return list(reversed(ring)) + [2.0 * R_W] + ring


def connection_factor(layer: int, skin: float = 0.0) -> float:
    r"""
    Connection transmissibility factor of the graded grid's well, carried over from the
    parent radial deck,

    .. math::

        T_c^{k} = \frac{2 \pi C \, (kh)_k}{\ln(r_1 / r_w) + s},

    where:

    - :math:`T_c^{k}`: the factor of the completion in layer :math:`k` (cp-RB/(d-psi)).
    - :math:`C = 0.001127`: the Darcy constant in field units; :math:`(kh)_k` the Table-3 permeability-thickness (md-ft).
    - :math:`r_1 = 0.8416\ \mathrm{ft}`: log-mean centre radius of the parent's innermost shell; :math:`r_w = 0.25` ft; :math:`s` the skin, zero here.
    """
    return 2.0 * np.pi * DARCY_FIELD_C * WELL_KH[layer] / (np.log(R1_LOGMEAN / R_W) + skin)


def report_steps(total_days: float = 900.0) -> list[float]:
    r"""
    The ``TSTEP`` increments (days): the first day partitioned geometrically,

    .. math::

        \Delta t^{n} = \Delta t^{0}\, r^{n}, \qquad
        \Delta t^{0} = \frac{r - 1}{r^{N} - 1}, \qquad n = 0, \dots, N - 1,

    rounded to :math:`10^{-6}` d, then 0.5 d steps to day 10, 2 d steps to day 100, 5 d steps
    to day 900 and 30 d steps to ``total_days`` beyond it.

    where:

    - :math:`N` (``TRANSIENT_STEPS``) and :math:`r` (``TRANSIENT_RATIO``): the number and ratio of the early steps, which resolve the near-well transient.
    """
    r, n = TRANSIENT_RATIO, TRANSIENT_STEPS
    a0 = (r - 1.0) / (r ** n - 1.0)
    steps = [float(v) for v in np.round(a0 * r ** np.arange(n), 6)]
    steps += [0.5] * 18 + [2.0] * 45
    steps += [5.0] * int(round((min(total_days, 900.0) - 100.0) / 5.0))
    steps += [30.0] * int(round(max(total_days - 900.0, 0.0) / 30.0))
    return steps


def sample_porosity(nx: int, ny: int, seed: int = POROSITY_SEED) -> np.ndarray:
    r"""
    The frozen per-cell porosity realisation of the heterogeneous deck,
    :math:`\phi_{ijk} = \max(\phi_{\min}, \tilde\phi_{ijk})`,
    :math:`\tilde\phi_{ijk} \sim \mathcal N(\phi_k, (\sigma_\phi \phi_k)^2)`, in the deck's storage
    order (:math:`x` fastest, :math:`z` slowest); :math:`\sigma_\phi = 0.10`.
    """
    rng = np.random.default_rng(seed)
    field = np.empty((NZ, ny, nx), dtype=float)
    for k, mean in enumerate(LAYER_PORO):
        field[k] = rng.normal(mean, POROSITY_CV * mean, size=(ny, nx))
    return np.maximum(field, POROSITY_FLOOR)


def _fmt(values, per_line: int, spec: str = "{:g}", indent: str = "   ") -> str:
    """Format a numeric sequence as indented deck lines with ``per_line`` items each."""
    tokens = [spec.format(float(v)) for v in values]
    return "\n".join(indent + " ".join(tokens[i:i + per_line])
                     for i in range(0, len(tokens), per_line))


def _layer_constant(values, n: int, spec: str = "{:g}") -> str:
    """One ``n*value`` repeat token per layer, five layers to a line."""
    tokens = [f"{n}*{spec.format(float(v))}" for v in values]
    return "\n".join("   " + "   ".join(tokens[i:i + 5]) for i in range(0, len(tokens), 5))


def _widths_block(widths: list[float]) -> str:
    if len(set(widths)) == 1:
        return f"   {len(widths)}*{widths[0]:g}"
    return _fmt(widths, 7, "{:g}")


def _steps_block(steps: list[float]) -> str:
    """The ``TSTEP`` list, eight to a line: the early steps to 1e-6 d, the rest as written."""
    tokens = [f"{t:.6f}" for t in steps[:TRANSIENT_STEPS]] + [f"{t:g}" for t in steps[TRANSIENT_STEPS:]]
    return "\n".join("   " + " ".join(tokens[i:i + 8]) for i in range(0, len(tokens), 8))


def _porosity_block(v: Variant, nx: int, ny: int) -> str:
    if v.porosity == "uniform":
        return ("-- Porosity at reference pressure 3600 psi, uniform per layer (Table 2).\n"
                f"PORO\n{_layer_constant(LAYER_PORO, nx * ny)} /")
    field = sample_porosity(nx, ny)
    stats = "\n".join(
        f"--   layer {k + 1:2d}: mean {LAYER_PORO[k]:.3f} -> realised mean {field[k].mean():.5f}, "
        f"sd {field[k].std(ddof=0):.5f}, min {field[k].min():.5f}, max {field[k].max():.5f}"
        for k in range(NZ))
    return ("-- Heterogeneous porosity: one frozen realisation, drawn once with\n"
            f"-- numpy default_rng(seed={POROSITY_SEED}) as\n"
            f"--   phi_ijk = max({POROSITY_FLOOR:g}, N(phi_k, ({POROSITY_CV:g}*phi_k)^2))\n"
            "-- with phi_k the Table-2 layer porosity.  Values are hard-coded below in\n"
            "-- Eclipse order (I fastest, then J, then K); no run-time randomness.\n"
            f"{stats}\nPORO\n{_fmt(field.ravel(), 10, '{:.5f}')} /")


def _completion_block(v: Variant, iw: int, jw: int) -> str:
    if v.grid == "graded":
        t7, t8 = connection_factor(7), connection_factor(8)
        return f"""\
-- Completed in layers 7 and 8 (Table 3), 0.5 ft wellbore diameter, zero skin.
-- The well cell is exactly the wellbore footprint (dx = dy = 2*rw), so Peaceman's
-- equivalent radius r_o = 0.198*dx = 0.099 ft falls inside rw and the geometric
-- well index is undefined.  Item 8 states the parent radial factor instead,
-- T = 2*pi*0.001127*Kh / (ln(r1/rw) + skin) with r1 = 0.8416 ft:
--   layer 7: Kh = 6200 md-ft -> T = {t7:.2f}
--   layer 8: Kh =  480 md-ft -> T = {t8:.2f}
-- so the Cartesian well reproduces the SPE-2 productivity index exactly.
COMPDAT
   'PROD' {iw} {jw} 7 7 'OPEN' 1* {t7:.2f} 0.5 1* 0 /
   'PROD' {iw} {jw} 8 8 'OPEN' 1* {t8:.2f}  0.5 1* 0 /
/"""
    return f"""\
-- Completed in layers 7 and 8 (Table 3), 0.5 ft wellbore diameter, zero skin.
-- The well cell is {EQUISPACED_DX:g} ft square, so Peaceman's equivalent radius
-- r_o = 0.198*dx = {0.198 * EQUISPACED_DX:.1f} ft lies well outside rw = 0.25 ft; item 8 is
-- defaulted and the simulator computes the factor from the cell's geometry.
COMPDAT
   'PROD' {iw} {jw} 7 7 'OPEN' 1* 1* 0.5 1* 0 /
   'PROD' {iw} {jw} 8 8 'OPEN' 1* 1* 0.5 1* 0 /
/"""


def build_deck(v: Variant) -> str:
    """The complete deck of one variant."""
    widths = cell_widths(v.grid)
    nx = ny = len(widths)
    iw = jw = nx // 2 + 1
    steps = report_steps(v.total_days)
    ray = "\n".join(f"   {iw + d} {jw + d} {k} /" for k in PERF_LAYERS for d in range(nx - iw + 1))
    grid_note = (
        "the Table-3 radial block boundaries (0.25 ... 2050 ft) mirrored about the\n"
        "--     well axis: logarithmically graded columns, the central one the 0.5 ft wellbore\n"
        "--     footprint" if v.grid == "graded" else
        f"{nx} columns of {EQUISPACED_DX:g} ft in each plan direction, the well in the central one")
    header = f"""\
-- =====================================================================
-- SPE-2 CARTESIAN SINGLE-WELL DRAWDOWN ({v.label})
-- Generated by data/spe2-cartesian/make_decks.py -- edit that file, not this one.
--
-- Cartesian re-gridding of the Second SPE Comparative Solution Project
--   H.G. Weinstein, J.E. Chappelear, J.S. Nolen, "Second Comparative
--   Solution Project: A Three-Phase Coning Study," JPT 38(3): 345-353,
--   March 1986.  SPE-10489-PA.
-- Parent radial deck: data/spe2/SPE2.DATA
--
-- Carried over from the parent: the 15 Table-2 layers (thickness, kx, kz = 0.1 kx,
-- porosity), PERMY = PERMX, the layer 7 + 8 completion with its 0.5 ft wellbore,
-- every fluid table (SWOF, SGOF, PVTO, PVDG, PVTW, DENSITY, ROCK, STONE1), the
-- contacts (GOC 9035 ft, WOC 9209 ft), the 3600 psia datum at the GOC, the 9000 ft
-- formation top and the 9110 ft BHP reference depth.
--
-- This variant:
--   * GRID: a 4100 x 4100 ft square in {nx} x {ny} x {NZ} = {nx * ny * NZ} blocks,
--     {grid_note}.
--   * POROSITY: {"layer-uniform (Table 2)" if v.porosity == "uniform" else "one frozen per-cell realisation about the Table-2 layer means"}.
--   * SCHEDULE: one oil-rate target of {v.oil_rate:g} STB/D with a {v.min_bhp:g} psia minimum
--     BHP for the whole {v.total_days:g} days, reported on a schedule graded for
--     well-test diagnostics.
-- ====================================================================="""
    return f"""\
{header}
RUNSPEC
-- ---------------------------------------------------------------------

TITLE
   SPE-2 CARTESIAN DRAWDOWN - {v.label}

DIMENS
   {nx} {ny} {NZ} /

OIL
WATER
GAS
-- Live oil with dissolved gas (black oil); no vaporized oil in SPE-2.
DISGAS

FIELD

START
   1 'JAN' 1982 /

WELLDIMS
-- 1 well, completed in 2 layers, 1 group, 1 well/group.
   1 2 1 1 /

TABDIMS
-- 1 sat-fn region, 1 PVT region; node counts sized for Tables 4 and 5.
   1 1 20 30 1 30 /

EQLDIMS
-- 1 equilibration region; raise the depth-node count for RSVD/initialisation.
   1 100 20 1 20 /

UNIFOUT

GRID
-- ---------------------------------------------------------------------
INIT

-- Column widths (ft), -x edge -> +x edge.
DXV
{_widths_block(widths)} /

-- Identical columns in y: the cross section is square about the well.
DYV
{_widths_block(widths)} /

-- Layer thicknesses (ft), top -> bottom, one value per layer (Table 2).
DZV
   {" ".join(f"{z:g}" for z in LAYER_DZ)} /

-- Depth to top of formation = 9000 ft (Table 3), flat over the {nx}x{ny} plan.
TOPS
   {nx * ny}*9000 /

-- Horizontal permeability kx (md) by layer, Table 2.
PERMX
{_layer_constant(LAYER_KX, nx * ny)} /

-- ky = kx, carrying over the parent deck's COPY behaviour.
COPY
   PERMX PERMY /
/

-- Vertical permeability kz (md) by layer, Table 2 (kz/kx = 0.1).
PERMZ
{_layer_constant(LAYER_KZ, nx * ny)} /

{_porosity_block(v, nx, ny)}

PROPS
-- ---------------------------------------------------------------------

-- Three-phase oil relative permeability by Stone's first method, as in the
-- parent radial deck.
STONE1

-- Water/oil saturation functions (Table 4): Sw, krw, krow, Pcow(psi).
SWOF
   0.22   0.00     1.0000   7.0
   0.30   0.07     0.4000   4.0
   0.40   0.15     0.1250   3.0
   0.50   0.24     0.0649   2.5
   0.60   0.33     0.0048   2.0
   0.80   0.65     0.0000   1.0
   0.90   0.83     0.0000   0.5
   1.00   1.00     0.0000   0.0 /

-- Gas/oil saturation functions (Table 4): Sg, krg, krog, Pcog(psi).
SGOF
   0.00   0.0000   1.00    0.0
   0.04   0.0000   0.60    0.2
   0.10   0.0220   0.33    0.5
   0.20   0.1000   0.10    1.0
   0.30   0.2400   0.02    1.5
   0.40   0.3400   0.00    2.0
   0.50   0.4200   0.00    2.5
   0.60   0.5000   0.00    3.0
   0.70   0.8125   0.00    3.5
   0.78   1.0000   0.00    3.9 /

-- Live-oil PVT (Table 5). Saturated branch: Rs(Mscf/STB) P(psia) Bo(RB/STB)
-- muo(cp), each node carrying one undersaturated point at 6000 psia built
-- from co = 1e-5 psi^-1 (Table 3) with constant undersaturated viscosity.
PVTO
   0.165   400    1.0120   1.17
           6000   0.95533  1.17 /
   0.335   800    1.0255   1.14
           6000   0.97217  1.14 /
   0.500   1200   1.0380   1.11
           6000   0.98818  1.11 /
   0.665   1600   1.0510   1.08
           6000   1.00476  1.08 /
   0.828   2000   1.0630   1.06
           6000   1.02048  1.06 /
   0.985   2400   1.0750   1.03
           6000   1.03630  1.03 /
   1.130   2800   1.0870   1.00
           6000   1.05222  1.00 /
   1.270   3200   1.0985   0.98
           6000   1.06774  0.98 /
   1.390   3600   1.1100   0.95
           6000   1.08336  0.95 /
   1.500   4000   1.1200   0.94
           6000   1.09760  0.94 /
   1.600   4400   1.1300   0.92
           6000   1.11192  0.92 /
   1.676   4800   1.1400   0.91
           6000   1.12632  0.91 /
   1.750   5200   1.1480   0.90
           6000   1.13882  0.90 /
   1.810   5600   1.1550   0.89
           6000   1.15038  0.89 /
/

-- Dry-gas PVT (Table 5): P(psia) Bg(RB/Mscf) mug(cp).
PVDG
   400    5.90   0.0130
   800    2.95   0.0135
   1200   1.96   0.0140
   1600   1.47   0.0145
   2000   1.18   0.0150
   2400   0.98   0.0155
   2800   0.84   0.0160
   3200   0.74   0.0165
   3600   0.65   0.0170
   4000   0.59   0.0175
   4400   0.54   0.0180
   4800   0.49   0.0185
   5200   0.45   0.0190
   5600   0.42   0.0195 /

-- Water PVT referenced at 3600 psi (Table 5): Bw = 1.00341 RB/STB,
-- Cw = 3e-6 psi^-1, muw = 0.96 cp, zero viscosibility.
PVTW
   3600   1.00341   3.0E-6   0.96   0.0 /

-- Surface densities (lbm/cu ft), Table 3: oil, water, gas.
DENSITY
   45.0   63.02   0.0702 /

-- Rock: reference pressure 3600 psi, pore compressibility 4e-6 psi^-1 (Table 3).
ROCK
   3600   4.0E-6 /

SOLUTION
-- ---------------------------------------------------------------------

-- Capillary/gravity equilibrium: 3600 psia at the GOC (9035 ft); WOC at
-- 9209 ft; reference Pc = 0 at each contact (Statement of the Problem).
EQUIL
--  datum  Pdatum  OWC    Pcow@OWC  GOC    Pcog@GOC  Rs(table) Rv  N
    9035   3600    9209   0.0       9035   0.0       1         0   0 /

-- Initial solution GOR constant through the oil column at the bubble-point
-- value for 3600 psi (1.390 Mscf/STB).
RSVD
   9000   1.390
   9359   1.390 /

-- Restart output at every report step, for the EDA/PINN state caches.
RPTRST
   BASIC=2 /

SUMMARY
-- ---------------------------------------------------------------------
-- Well-test observables for the drawdown analysis.
WBHP
/
WOPR
/
WWPR
/
WGPR
/
WWCT
/
WGOR
/
-- Well-block and 9-block averaged pressures (Horner / MDH reference levels).
WBP
/
WBP9
/
-- Block pressures along the ray from the well column to the corner, in the two
-- perforated layers.
BPR
{ray}
/
-- Field averages and fluids in place.
FPR
FOIP
FWIP
FGIP

SCHEDULE
-- ---------------------------------------------------------------------

-- Central producer in column (I,J) = ({iw},{jw}); BHP reference at the Table-3
-- pump depth 9110 ft.
WELSPECS
   'PROD' 'G1' {iw} {jw} 9110 'OIL' /
/

{_completion_block(v, iw, jw)}

-- Numerical controls only: start from a 1e-4 day step so the early reports are
-- resolved, and cap the internal step at 5 days.
TUNING
   0.0001 5.0 /
   /
   /

-- One oil-rate target of {v.oil_rate:g} STB/D for the whole {v.total_days:g} days, with a
-- {v.min_bhp:g} psia minimum BHP.
WCONPROD
   'PROD' 'OPEN' 'ORAT' {v.oil_rate:g} 4* {v.min_bhp:g} /
/

-- {len(steps)} report steps: {TRANSIENT_STEPS} geometric steps over day 1, then 0.5 d to day 10,
-- 2 d to day 100, 5 d to day {min(v.total_days, 900.0):g}{f" and 30 d to day {v.total_days:g}" if v.total_days > 900 else ""}.
TSTEP
{_steps_block(steps)} /

END
"""


def main(names: list[str]) -> None:
    """Write the named variants' decks (every variant when none is named) next to this script."""
    here = Path(__file__).resolve().parent
    for name in names or VARIANTS:
        v = VARIANTS[name]
        path = here / v.folder / v.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(build_deck(v))
        print(f"{name}: {path.relative_to(here)}")


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
