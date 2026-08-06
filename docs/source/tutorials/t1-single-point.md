# T1 — Single-point energy of a crystal

**Goal.** Compute the total energy of bulk silicon at a fixed geometry, and
understand every line of the input that produced it.

**Prerequisites.** [Getting started](../getting-started/index.md) complete, and
an SKF set covering Si. Set `SKF_DIR` to it.

**Time.** About five minutes; the calculation itself takes seconds.

:::{note}
The numbers shown below come from an actual run, using a full periodic-table
parameter set. With a different set — `pbc-0-3`, say — the shape of the output
will be identical and the energies will differ. That is expected: the parameter
set *is* part of the physics.
:::

## Step 1 — the geometry

A periodic structure needs lattice vectors, so this is a GEN file in fractional
form (`F`) rather than the cluster form (`C`) used for molecules:

```text
2  F
  Si
    1 1   0.00000000   0.00000000   0.00000000
    2 1   0.25000000   0.25000000   0.25000000
    0.00000000   0.00000000   0.00000000
    0.00000000   2.71350000   2.71350000
    2.71350000   0.00000000   2.71350000
    2.71350000   2.71350000   0.00000000
```

Reading it: two atoms, fractional coordinates, one species (`Si`); then one line
per atom (index, species number, coordinates); then an origin line; then the
three lattice vectors in Å. This is the primitive cell of diamond-structure
silicon with a lattice constant of 5.427 Å.

## Step 2 — the script

```python
#!/usr/bin/env python
"""T1: single-point energy of bulk silicon."""

import os

from aiida import engine, orm
from aiida.plugins import CalculationFactory, DataFactory

SKF_DIR = os.environ["SKF_DIR"].rstrip("/") + "/"

GEOMETRY = (
    "2  F\n"
    "  Si\n"
    "    1 1   0.00000000   0.00000000   0.00000000\n"
    "    2 1   0.25000000   0.25000000   0.25000000\n"
    "    0.00000000   0.00000000   0.00000000\n"
    "    0.00000000   2.71350000   2.71350000\n"
    "    2.71350000   0.00000000   2.71350000\n"
    "    2.71350000   2.71350000   0.00000000"
)

parameters = DataFactory("dftbplus")({
    "Geometry": {"GenFormat": {"_raw": GEOMETRY}},
    "Hamiltonian": {"DFTB": {
        "SCC": True,
        "SCCTolerance": 1e-5,
        "MaxSCCIterations": 100,
        "_raw_1": (
            'SlaterKosterFiles = Type2FileNames {\n'
            f'  Prefix = "{SKF_DIR}"\n'
            '  Separator = "-"\n  Suffix = ".skf"\n}'
        ),
        "_raw_2": 'MaxAngularMomentum {\n  Si = "d"\n}',
        "_raw_3": (
            "KPointsAndWeights = SupercellFolding {\n"
            "  4 0 0\n  0 4 0\n  0 0 4\n  0.5 0.5 0.5\n}"
        ),
        "_raw_4": 'Filling = Fermi {\n  Temperature [K] = 300\n}',
    }},
    "Analysis": {"CalculateForces": True},
    "Options": {},
    "ParserOptions": {"ParserVersion": 12},
})

results, node = engine.run_get_node(
    CalculationFactory("dftbplus"),
    code=orm.load_code("dftb+@localhost"),
    parameters=parameters,
    use_remote_skf_path=orm.Bool(True),
    structure=orm.Dict({"formula": "Si2", "note": "diamond primitive cell"}),
    metadata={"options": {"max_wallclock_seconds": 900, "withmpi": False}},
)

print("exit status:", node.exit_status)
for key, value in results["output_parameters"].get_dict().items():
    print(f"  {key}: {value}")
```

Four blocks deserve a word:

`MaxAngularMomentum { Si = "d" }`
: **Mandatory.** The value comes from the parameter set's documentation. A
  cross-check: the first numeric field on line 2 of `Si-Si.skf` is `Ed`, and it
  is non-zero, so the file carries d functions.

`KPointsAndWeights = SupercellFolding`
: A periodic system needs a k-point mesh. The 4×4×4 mesh with the
  `0.5 0.5 0.5` shift is a Monkhorst–Pack grid. Without this block DFTB+
  samples Γ only, which for a two-atom cell is not enough.

`Filling = Fermi { Temperature [K] = 300 }`
: Fractional occupations, so a small gap or a metal does not oscillate between
  SCC steps.

`ParserOptions { ParserVersion = 12 }`
: Pins the input dialect. Newer DFTB+ versions convert it and warn about
  renamed keywords (`CalculateForces` → `PrintForces`); the conversion is
  automatic and the calculation is unaffected.

## Step 3 — run it

```shell
verdi run t1_silicon.py
```

## Step 4 — the output

```text
exit status: 0
  total_energy_H: -2.5508052845
  total_energy_eV: -69.410947834837
  fermi_energy_eV: -3.7362850869386
  scc_converged: True
  forces_eV_Ang: [[0.042033776323667, 0.042033776323667, 0.042033776323667],
                  [-0.042033776323667, -0.042033776323667, -0.042033776323667]]
  max_force_eV_Ang: 0.072804636226578
```

Read it as follows:

- **`total_energy_H` / `total_energy_eV`** — the same number twice, in Hartree
  as DFTB+ printed it and in eV using the CODATA 2018 conversion. DFTB total
  energies are not comparable across parameter sets; differences within one set
  are the meaningful quantity.
- **`fermi_energy_eV`** — present because the system is periodic.
- **`scc_converged: True`** — the charges converged within `SCCTolerance`.
- **`forces_eV_Ang`** — one `[Fx, Fy, Fz]` per atom, converted from Ha/Bohr.
- **`max_force_eV_Ang`** — the largest force *magnitude*, `0.0728`, not the
  largest component `0.042`: √3 × 0.042 = 0.0728. The two atoms push against
  each other along the body diagonal, which tells you this fixed geometry is not
  the equilibrium one for these parameters. Relaxing it is [T2](t2-relaxation.md).

## Step 5 — look at what else came back

```shell
verdi process list -a -p 1
verdi calcjob outputls <PK>
```

```text
_scheduler-stderr.txt  _scheduler-stdout.txt  band.out  charges.bin
detailed.out  dftb.err  dftb.out  dftb_pin.hsd
```

Worth knowing:

- **`charges.bin`** — the converged charges. [T3](t3-band-structure.md) restarts
  from exactly this file instead of redoing the SCC cycle.
- **`dftb_pin.hsd`** — DFTB+'s *processed* input: every default it filled in,
  written out explicitly. When a run does something you did not expect, diff
  this against your `dftb_in.hsd`.
- **`band.out`** — eigenvalues at the k-points that were sampled. The plugin
  retrieves it but does not parse it.
- No `geom.out.*` — nothing moved, so DFTB+ wrote no relaxed geometry.

## What you learned

- A periodic input needs a GEN file in `F` form, a k-point mesh, and a filling
  scheme; a molecule needs none of the three.
- `MaxAngularMomentum` is mandatory and set-specific, and the SKF file itself
  can confirm it.
- `max_force_eV_Ang` is a magnitude, and it tells you whether the geometry is
  converged before you run anything else.
- Only some of `detailed.out` is parsed; the rest stays in `retrieved`.

Next: [T2 — geometry relaxation](t2-relaxation.md).
