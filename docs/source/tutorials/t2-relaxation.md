# T2 — Geometry relaxation

**Goal.** Relax a deliberately distorted water molecule, then read the relaxed
coordinates back out of the database.

**Prerequisites.** [T1](t1-single-point.md), and an SKF set covering O and H.

**Time.** Five minutes.

## Step 1 — a bad starting geometry

Water with both O–H bonds at 1.10 Å and a 90° angle. Wrong on both counts, which
is the point — the relaxation has something to do:

```text
3  C
  O H
    1 1   0.00000000   0.00000000   0.00000000
    2 2   0.00000000   0.00000000   1.10000000
    3 2   1.10000000   0.00000000   0.00000000
```

`C` for cluster: no lattice vectors, no k-points. Species are numbered in the
order of the second line, so `1` is O and `2` is H.

## Step 2 — add a Driver

A DFTB+ input with no `Driver` block is a static calculation. Adding one turns
it into a relaxation:

```python
parameters = DataFactory("dftbplus")({
    "Geometry": {"GenFormat": {"_raw": GEOMETRY}},
    "Driver": {"ConjugateGradient": {
        "MovedAtoms": "1:-1",
        "MaxForceComponent": 1e-4,
        "MaxSteps": 100,
        "OutputPrefix": "./",
    }},
    "Hamiltonian": {"DFTB": {
        "SCC": True,
        "SCCTolerance": 1e-5,
        "MaxSCCIterations": 100,
        "_raw_1": (
            'SlaterKosterFiles = Type2FileNames {\n'
            f'  Prefix = "{SKF_DIR}"\n'
            '  Separator = "-"\n  Suffix = ".skf"\n}'
        ),
        "_raw_2": 'MaxAngularMomentum {\n  O = "p"\n  H = "s"\n}',
    }},
    "Analysis": {"CalculateForces": True},
    "Options": {},
    "ParserOptions": {"ParserVersion": 12},
})
```

`{"ConjugateGradient": {...}}` — a single-key dictionary whose value is another
dictionary — serialises to a *named typed block*:

```text
Driver = ConjugateGradient {
  MovedAtoms = "1:-1"
  MaxForceComponent = 0.0001
  MaxSteps = 100
  OutputPrefix = "./"
}
```

`MovedAtoms = "1:-1"` means every atom. `MaxForceComponent` is the convergence
threshold in atomic units (Ha/Bohr), not eV/Å.

:::{admonition} The output prefix trap
:class: important

`OutputPrefix = "./"` is what most DFTB+ examples carry, and with it DFTB+ never
writes a retrievable relaxed geometry — so nothing comes back. The plugin
rewrites it to `OutputPrefix = "geom.out"` before writing the file, which is why
`geom.out.gen` and `geom.out.xyz` end up in the retrieve list.

That rewrite is controlled by the `fix_output_prefix` input, which defaults to
`True`. If you set your own meaningful prefix it is left alone; if you set
`fix_output_prefix=False` and keep `./`, you get no geometry back.
:::

Run it exactly as in T1.

## Step 3 — the output

```text
exit status: 0
  total_energy_H: -4.0201353089
  total_energy_eV: -109.39345465161
  fermi_energy_eV: 0.68910010037617
  scc_converged: True
  forces_eV_Ang: [[-0.0011099597760775, -0.0, -0.0011099596218113],
                  [8.9509055882286e-05, 0.0, 0.001020450617351],
                  [0.0010204506687731, 0.0, 8.9509055882286e-05]]
  max_force_eV_Ang: 0.0015697200599347
```

`max_force_eV_Ang` has dropped to ~1.6 × 10⁻³ eV/Å. **The parsed values are the
last geometry step**, not the first: `detailed.out` contains one block per step
and the parser deliberately takes the last one.

The retrieve list now has two more entries:

```shell
verdi calcjob outputls <PK>
```

```text
_scheduler-stderr.txt  _scheduler-stdout.txt  band.out  charges.bin
detailed.out  dftb.err  dftb.out  dftb_pin.hsd  geom.out.gen  geom.out.xyz
```

## Step 4 — read the relaxed structure back

```python
from aiida import orm

node = orm.load_node(<PK>)

with node.outputs.retrieved.open("geom.out.gen") as handle:
    print(handle.read())

with node.outputs.retrieved.open("geom.out.xyz") as handle:
    print(handle.read())
```

```text
 3  C
 O H
    1  1    0.7017710393E-01   -0.5138588122E-15    0.7017710393E-01
    2  2   -0.2525111499E-01    0.5521625163E-15    0.1055074011E+01
    3  2    0.1055074011E+01   -0.3830370412E-16   -0.2525111499E-01
```

```text
    3
Geometry Step: 10
    O      0.07017710     -0.00000000      0.07017710      6.50960012
    H     -0.02525111      0.00000000      1.05507401      0.74519994
    H      1.05507401     -0.00000000     -0.02525111      0.74519994
```

The XYZ header tells you it took **10 geometry steps**, and the fourth column is
the Mulliken charge on each atom — 6.51 electrons on oxygen against a neutral
6.0, so about half an electron drawn from each hydrogen. Checking the geometry
that came out:

```python
import math

o = (0.07017710, 0.0, 0.07017710)
h1 = (-0.02525111, 0.0, 1.05507401)
h2 = (1.05507401, 0.0, -0.02525111)

def distance(a, b):
    return math.dist(a, b)

def angle(centre, a, b):
    va = [x - c for x, c in zip(a, centre)]
    vb = [x - c for x, c in zip(b, centre)]
    cos = sum(x * y for x, y in zip(va, vb)) / (math.dist(a, centre) * math.dist(b, centre))
    return math.degrees(math.acos(cos))

print(f"O-H  {distance(o, h1):.3f} A, {distance(o, h2):.3f} A")
print(f"angle {angle(o, h1, h2):.1f} deg")
```

```text
O-H  0.990 A, 0.990 A
angle 101.1 deg
```

Compare with experiment: 0.958 Å and 104.5°. The bond is ~3 % long and the angle
3° narrow. That is a normal DFTB result for water, and a fair illustration of
what the method costs you — see [the DFTB primer](../explanation/dftb-primer.md).

## Step 5 — the geometry is *not* a structure node

`geom.out.gen` is a file inside `retrieved`, not a
{class}`~aiida.orm.nodes.data.structure.StructureData`. The plugin creates no
structure nodes at all. To chain a second calculation onto the relaxed geometry,
read the text and feed it back in:

```python
with node.outputs.retrieved.open("geom.out.gen") as handle:
    relaxed = handle.read().rstrip()

next_parameters = parameters.get_dict()
next_parameters["Geometry"] = {"GenFormat": {"_raw": relaxed}}
next_parameters.pop("Driver")           # static calculation this time
```

That is exactly what a `WorkChain` would automate — [T6](t6-custom-workchain.md).
To convert the geometry into ASE or pymatgen objects instead, see
[Export structures and results](../how-to/export-structures.md).

## What you learned

- A `Driver` block turns a static calculation into a relaxation; the single-key
  dict form produces the `Driver = ConjugateGradient { ... }` spelling.
- `OutputPrefix = "./"` would lose the relaxed geometry; the plugin rewrites it,
  and that behaviour is a switchable input.
- Parsed values are always the **last** geometry step.
- The relaxed structure comes back as a file, not as a node — this plugin has no
  `StructureData` support.

Next: [T3 — band structure](t3-band-structure.md).
