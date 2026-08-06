# Your first calculation

Goal: from a working profile to a finished DFTB+ run with parsed results, on
the simplest possible system — an H₂ molecule. Ten minutes, no cluster.

**You need:** the four things from [Prerequisites](prerequisites.md), and an SKF
set containing `H-H.skf`. Any set that covers hydrogen will do; the output below
comes from a real run, so your energies will match only if you use the same set.
What must match is the *shape* of everything you see.

## Step 1 — check the pieces

```shell
verdi status
verdi code list
ls "$SKF_DIR"/H-H.skf
```

Expected: `verdi status` green except possibly the daemon, your DFTB+ code
listed, and the file found. Set `SKF_DIR` to your set's directory:

```shell
export SKF_DIR=$HOME/skf/mio-1-1
```

## Step 2 — write the submission script

Save this as `run_h2.py`. It is complete: nothing is elided.

```python
#!/usr/bin/env python
"""Single-point DFTB+ calculation on H2, run through AiiDA."""

import os

from aiida import engine, orm
from aiida.plugins import CalculationFactory, DataFactory

SKF_DIR = os.environ["SKF_DIR"].rstrip("/") + "/"   # trailing slash matters
CODE = "dftb+@localhost"

DftbParameters = DataFactory("dftbplus")

parameters = DftbParameters({
    "Geometry": {
        "GenFormat": {
            "_raw": (
                "2  C\n"
                "  H\n"
                "     1 1    0.0000000000E+00   0.0000000000E+00   0.0000000000E+00\n"
                "     2 1    0.0000000000E+00   0.0000000000E+00   0.7500000000E+00"
            )
        }
    },
    "Hamiltonian": {
        "DFTB": {
            "SCC": True,
            "MaxSCCIterations": 100,
            "SCCTolerance": 1e-5,
            "_raw_1": (
                'SlaterKosterFiles = Type2FileNames {\n'
                f'  Prefix = "{SKF_DIR}"\n'
                '  Separator = "-"\n'
                '  Suffix = ".skf"\n'
                '}'
            ),
            "_raw_2": 'MaxAngularMomentum {\n  H = "s"\n}',
        }
    },
    "Analysis": {"CalculateForces": True},
    "Options": {},
    "ParserOptions": {"ParserVersion": 12},
})

print("--- dftb_in.hsd that will be written ---")
print(parameters.get_hsd())

inputs = {
    "code": orm.load_code(CODE),
    "parameters": parameters,
    # the SKF files already sit at SKF_DIR on this machine: keep the absolute
    # path in the input and upload nothing
    "use_remote_skf_path": orm.Bool(True),
    "structure": orm.Dict({"formula": "H2", "skf_set": os.path.basename(SKF_DIR.rstrip("/"))}),
    "metadata": {
        "description": "H2 single point, first calculation",
        "options": {"max_wallclock_seconds": 600, "withmpi": False},
    },
}

results, node = engine.run_get_node(CalculationFactory("dftbplus"), **inputs)

print(f"--- finished: exit status {node.exit_status} ---")
print("retrieved:", node.outputs.retrieved.list_object_names())
if "output_parameters" in results:
    for key, value in results["output_parameters"].get_dict().items():
        print(f"  {key}: {value}")
```

Two details worth pausing on:

- **`_raw_1` and `_raw_2`.** Anything the dictionary form does not express goes
  through verbatim under a key starting with `_raw`. The key is dropped; the
  value is written as-is. That is how the Slater–Koster block and
  `MaxAngularMomentum` get in.
- **`use_remote_skf_path=True`.** The files stay where they are and the absolute
  path survives into `dftb_in.hsd`. The alternative — shipping the files with
  the job — is on the [SKF page](skf-parameter-sets.md#two-ways-to-supply-the-files).

## Step 3 — run it

`engine.run_get_node` runs the calculation in the current process and blocks
until it finishes. No daemon needed, which is why this is the first thing to
try:

```shell
verdi run run_h2.py
```

## Step 4 — read what happened

First, the input the plugin generated:

```text
--- dftb_in.hsd that will be written ---
Geometry = GenFormat {
  2  C
    H
       1 1    0.0000000000E+00   0.0000000000E+00   0.0000000000E+00
       2 1    0.0000000000E+00   0.0000000000E+00   0.7500000000E+00
}
Hamiltonian = DFTB {
  SCC = Yes
  MaxSCCIterations = 100
  SCCTolerance = 1e-05
  SlaterKosterFiles = Type2FileNames {
  Prefix = "/home/you/skf/mio-1-1/"
  Separator = "-"
  Suffix = ".skf"
}
  MaxAngularMomentum {
  H = "s"
}
}
Analysis {
  CalculateForces = Yes
}
Options {}
ParserOptions {
  ParserVersion = 12
}
```

`True` became `Yes`, the float became `1e-05`, and the raw blocks came through
untouched — including their original indentation, which is why the closing
braces of the raw blocks sit at column 0. HSD does not care.

Then the result:

```text
--- finished: exit status 0 ---
retrieved: ['_scheduler-stderr.txt', '_scheduler-stdout.txt', 'band.out',
            'charges.bin', 'detailed.out', 'dftb.err', 'dftb.out', 'dftb_pin.hsd']
  total_energy_H: -0.7139218279
  total_energy_eV: -19.426802608429
  fermi_energy_eV: -1.8719920539262
  scc_converged: True
  forces_eV_Ang: [[-0.0, -0.0, 0.018609091221308], [-0.0, -0.0, -0.018609091221308]]
  max_force_eV_Ang: 0.018609091221308
```

Three things to notice:

1. **Exit status 0** means the parser found no failure signature. Anything else
   is one of [four exit codes](../reference/exit-codes.md).
2. **`geom.out.gen` is not in the list.** This was a static calculation, so DFTB+
   never wrote one. The plugin asks for eight files and gets the ones that exist;
   missing ones are not an error.
3. **`n_scc_iterations` is missing** from the parsed values. Recent DFTB+ versions
   no longer print the line the parser looks for in `detailed.out`. Nothing is
   lost — the SCC table is in `dftb.out` — but the key is absent. See
   [known gaps](../reference/exit-codes.md#known-parsing-gaps).

## Step 5 — inspect it with verdi

Everything is in the database now. The PK was printed by `verdi run`; use it:

```shell
verdi process list -a -p 1            # all processes from the last day
verdi process show <PK>               # inputs, outputs, and how it went
verdi calcjob res <PK>                # the parsed scalars, as JSON
verdi calcjob outputls <PK>           # every retrieved file
verdi calcjob outputcat <PK> detailed.out | head -40
verdi calcjob inputcat <PK> dftb_in.hsd
```

`verdi process show` prints the provenance: which code, which parameter node,
what came out. That table *is* the record of the calculation — it can be
re-read years later without your script.

The `detailed.out` you just printed contains rather more than the plugin parses:

```text
Fermi level:                        -0.0687944391 H           -1.8720 eV
Total energy:                       -0.7139218279 H          -19.4268 eV
Repulsive energy:                    0.0184556692 H            0.5022 eV
SCC converged
Total Forces
    1     -0.000000000000     -0.000000000000      0.000361889207
    2     -0.000000000000     -0.000000000000     -0.000361889207
Dipole moment:    0.00000000    0.00000000    0.00000000 Debye
```

The parser lifts the total energy, the Fermi level, the SCC verdict and the
forces (converting Ha/Bohr to eV/Å). Everything else stays in the file, which is
stored for ever on the `retrieved` node — you can parse the dipole moment
yourself at any time without re-running anything.

## Step 6 — check the parameters are queryable

This is the whole point of storing the input as a dictionary:

```shell
verdi data dftbplus list
verdi data dftbplus hsd <parameters-PK>
```

```python
from aiida.orm import QueryBuilder
from aiida.plugins import DataFactory

query = QueryBuilder()
query.append(DataFactory("dftbplus"), filters={"attributes.Hamiltonian.DFTB.SCC": True})
print(query.count(), "calculations were run with SCC enabled")
```

## What you learned

- The DFTB+ input is a nested Python dict; `_raw*` keys pass anything through.
- `engine.run_get_node` runs without a daemon; the PK is your handle afterwards.
- Eight output files are retrieved; four to six scalars are parsed out of
  `detailed.out`; everything else stays available in `retrieved`.
- Exit status 0 means "no known failure signature", not "physically sensible" —
  that judgement is still yours.

Next: [the verification checklist](verification.md), or straight into
[Tutorial 1](../tutorials/t1-single-point.md), which does the same thing on a
system with more than one element.
