# Entry points

Entry points are how AiiDA discovers a plugin. There is no registration step and
no configuration file: `pip install` writes them into the package metadata, and
AiiDA reads them from there.

## The four

```{list-table}
:header-rows: 1
:widths: 24 12 30 34

* - Group
  - Name
  - Object
  - What it gives you
* - `aiida.calculations`
  - `dftbplus`
  - `aiida_dftbplus.calculations:DftbPlusCalculation`
  - `CalculationFactory('dftbplus')`, and `--default-calc-job-plugin dftbplus`
* - `aiida.parsers`
  - `dftbplus`
  - `aiida_dftbplus.parsers:DftbPlusParser`
  - `metadata.options.parser_name = 'dftbplus'` — the calculation's default
* - `aiida.data`
  - `dftbplus`
  - `aiida_dftbplus.data:DftbParameters`
  - `DataFactory('dftbplus')`, and the node type in the database
* - `aiida.cmdline.data`
  - `dftbplus`
  - `aiida_dftbplus.cli:data_cli`
  - `verdi data dftbplus list / export / hsd`
```

All four share the name `dftbplus`, which is why every factory call in the
documentation uses that one string.

There is **no `aiida.workflows` entry point** — the plugin ships no `WorkChain`.
See [T6](../tutorials/t6-custom-workchain.md) for writing your own.

## Where they are declared

`pyproject.toml`:

```toml
[project.entry-points."aiida.data"]
"dftbplus" = "aiida_dftbplus.data:DftbParameters"

[project.entry-points."aiida.calculations"]
"dftbplus" = "aiida_dftbplus.calculations:DftbPlusCalculation"

[project.entry-points."aiida.parsers"]
"dftbplus" = "aiida_dftbplus.parsers:DftbPlusParser"

[project.entry-points."aiida.cmdline.data"]
"dftbplus" = "aiida_dftbplus.cli:data_cli"
```

## Verify they load

```shell
verdi plugin list aiida.calculations | grep dftbplus
verdi plugin list aiida.parsers      | grep dftbplus
verdi plugin list aiida.data         | grep dftbplus
verdi data dftbplus --help
verdi plugin list aiida.calculations dftbplus     # the full input spec
```

CI runs the same check against the built wheel in a clean virtual environment,
because a wheel that installs but whose entry points do not load is useless to
AiiDA:

```python
from importlib.metadata import entry_points

for group, name in {
    "aiida.calculations": "dftbplus",
    "aiida.parsers": "dftbplus",
    "aiida.data": "dftbplus",
    "aiida.cmdline.data": "dftbplus",
}.items():
    (ep,) = [e for e in entry_points(group=group) if e.name == name]
    ep.load()
```

## Why load through the factories

```python
from aiida.plugins import CalculationFactory, DataFactory

DftbPlusCalculation = CalculationFactory("dftbplus")
DftbParameters = DataFactory("dftbplus")
```

rather than importing the classes directly. Two reasons:

1. **The database stores the entry-point name**, not the import path. A node
   loaded from the database is reconstructed through the registry, so code that
   uses the registry and code that reads the database agree by construction.
2. **It keeps the dependency graph acyclic.** `parsers.py` needs the calculation
   class to type-check the node it is parsing; importing it directly would
   couple the two modules, so it goes through `CalculationFactory` instead.

## Renaming would be a breaking change

The entry-point name is written into every stored node's `process_type`. Change
`dftbplus` to something else and existing databases can no longer resolve their
own nodes. Treat these four strings as public API.
