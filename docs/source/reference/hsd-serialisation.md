# HSD serialisation rules

How `DftbPlusCalculation._dict_to_hsd` turns a Python dictionary into
`dftb_in.hsd`. Every rule, with an example.

## Scalars

```{list-table}
:header-rows: 1
:widths: 42 58

* - Python
  - HSD
* - `{"SCC": True}`
  - `SCC = Yes`
* - `{"ReadInitialCharges": False}`
  - `ReadInitialCharges = No`
* - `{"MaxSCCIterations": 250}`
  - `MaxSCCIterations = 250`
* - `{"SCCTolerance": 1e-5}`
  - `SCCTolerance = 1e-05`
* - `{"Prefix": "/opt/skf/"}`
  - `Prefix = "/opt/skf/"`
```

`bool` is tested before `int` — in Python `bool` is a subclass of `int`, and the
reverse order would write `SCC = 1`, which DFTB+ rejects. Floats use `%g`, so
`1e-5` becomes `1e-05` and `0.0001` becomes `0.0001`. Strings are **always**
quoted.

## Lists

```{list-table}
:header-rows: 1
:widths: 42 58

* - Python
  - HSD
* - `{"KPoints": [4, 4, 4]}`
  - `KPoints = 4 4 4`
* - `{"Lattice": [[1.0, 0.0], [0.0, 1.0]]}`
  - `Lattice {` / `  1 0` / `  0 1` / `}`
```

A flat list goes on one line; a list of lists becomes a block with one row per
line, each number formatted with `%g`.

## Blocks

```{list-table}
:header-rows: 1
:widths: 42 58

* - Python
  - HSD
* - `{"Options": {}}`
  - `Options {}`
* - `{"Optimizer": {"Rational": {}}}`
  - `Optimizer = Rational {}`
* - `{"Filling": {"Fermi": {"Temperature [K]": 300}}}`
  - `Filling = Fermi {` / `  Temperature [K] = 300` / `}`
* - `{"Analysis": {"PrintForces": True, "CalculateForces": True}}`
  - `Analysis {` / `  PrintForces = Yes` / `  CalculateForces = Yes` / `}`
```

The rule that surprises people: a **single-key** dictionary whose value is
another dictionary produces a *named typed block* (`Key = TypeName { ... }`),
because that is how DFTB+ spells a choice of method. A **multi-key** dictionary
produces an anonymous block (`Key { ... }`). So:

```python
{"Driver": {"ConjugateGradient": {"MaxSteps": 100}}}   # Driver = ConjugateGradient { MaxSteps = 100 }
{"Driver": {"MaxSteps": 100, "MaxForce": 1e-4}}        # Driver { MaxSteps = 100 ... }
```

A single-key dictionary whose value is a **scalar** gives an anonymous block:

```python
{"ParserOptions": {"ParserVersion": 12}}               # ParserOptions { ParserVersion = 12 }
```

## Raw passthrough

```{list-table}
:header-rows: 1
:widths: 42 58

* - Python
  - HSD
* - `{"Geometry": {"GenFormat": {"_raw": "2 C\\n H\\n..."}}}`
  - `Geometry = GenFormat {` / `  <text verbatim>` / `}`
* - `{"_raw_1": "Analysis { PrintForces = Yes }"}`
  - `Analysis { PrintForces = Yes }`
* - `{"_healing": {...}}`
  - *(nothing — skipped)*
```

Three distinct behaviours for underscore keys:

**`_raw` as a dictionary's only key** — its value fills the block body,
line by line, at the block's indentation. This is how geometry gets in.

**A key starting with `_raw`** (`_raw_1`, `_raw_mixer`, ...) — the *value* is
written as a line at the current indentation and the key vanishes. This is how
any construct the dictionary form cannot express gets in. Numbering keeps them
distinct; Python preserves insertion order, so that is also the file order.

**Any other key starting with `_`** — skipped entirely. Metadata you want stored
and queryable but never sent to DFTB+.

:::{note}
Raw text is written **exactly as given** — it is not re-indented to the
surrounding block. A multi-line raw block therefore often has its closing brace
at column 0 inside an indented block. HSD does not care, and preserving the text
byte-for-byte is the point.
:::

## A complete example

```python
{
    "Geometry": {"GenFormat": {"_raw": "2  C\n  H\n  1 1 0.0 0.0 0.0\n  2 1 0.0 0.0 0.75"}},
    "Hamiltonian": {"DFTB": {
        "SCC": True,
        "MaxSCCIterations": 100,
        "SCCTolerance": 1e-5,
        "_raw_1": 'SlaterKosterFiles = Type2FileNames {\n  Prefix = "/opt/skf/"\n  Separator = "-"\n  Suffix = ".skf"\n}',
        "_raw_2": 'MaxAngularMomentum {\n  H = "s"\n}',
    }},
    "Analysis": {"CalculateForces": True},
    "Options": {},
    "ParserOptions": {"ParserVersion": 12},
}
```

```text
Geometry = GenFormat {
  2  C
    H
    1 1 0.0 0.0 0.0
    2 1 0.0 0.0 0.75
}
Hamiltonian = DFTB {
  SCC = Yes
  MaxSCCIterations = 100
  SCCTolerance = 1e-05
  SlaterKosterFiles = Type2FileNames {
  Prefix = "/opt/skf/"
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

## The two post-processing patches

Applied to the text *after* serialisation, before `dftb_in.hsd` is written:

```{list-table}
:header-rows: 1
:widths: 26 20 54

* - Patch
  - When
  - Effect
* - `_fix_output_prefix`
  - `fix_output_prefix=True` (default)
  - `OutputPrefix = "./"` → `OutputPrefix = "geom.out"`. A prefix that already names something is untouched.
* - `_patch_skf_paths`
  - `skf_files` given and `use_remote_skf_path=False`
  - `Prefix = "/abs/path/"` → `Prefix = "./"`, in every quoting style, and the same for `SlaterKosterFiles = "..."`.
```

`get_hsd()` and `verdi data dftbplus hsd` show the text **before** these
patches. To see the file as written, use `verdi calcjob inputcat <PK>
dftb_in.hsd`.

## Checking your own dictionary

```python
from aiida_dftbplus.calculations import DftbPlusCalculation

print(DftbPlusCalculation._dict_to_hsd(my_dict))
```

No profile, no database, no DFTB+ — a pure function over the dictionary. It is
the fastest way to find out what a nesting choice will produce.
