---
sd_hide_title: true
---

# aiida-dftbplus

:::{div} sd-text-center sd-fs-3 sd-font-weight-bold
aiida-dftbplus
:::

:::{div} sd-text-center sd-fs-5
Run [DFTB+](https://dftbplus.org) from [AiiDA](https://www.aiida.net), with full provenance.
:::

---

`aiida-dftbplus` wraps one DFTB+ execution as an AiiDA {class}`~aiida.engine.processes.calcjobs.calcjob.CalcJob`:
it writes `dftb_in.hsd`, stages the Slater–Koster files, submits the job through
AiiDA's scheduler and transport layer, brings every output file back, and parses
the energies and forces into a queryable {class}`~aiida.orm.nodes.data.dict.Dict`
node. Because the DFTB+ input is stored as a **nested Python dictionary** rather
than an opaque text file, every setting of every calculation you ever ran stays
searchable in the database.

One calculation in, one calculation out — this plugin ships **no workflows and no
automatic error recovery**. See [Scope and limitations](#scope-and-limitations)
below before you plan a campaign around it.

## Install

```shell
pip install aiida-dftbplus
```

## A calculation in ten lines

Assumes a working AiiDA profile, a DFTB+ code registered as `dftb+@localhost`,
and the `mio-1-1` Slater–Koster set on the same machine — all three are set up
in [Getting started](getting-started/index.md).

```python
from aiida import engine, orm
from aiida.plugins import CalculationFactory, DataFactory

parameters = DataFactory("dftbplus")({
    "Geometry": {"GenFormat": {"_raw": "2  C\n  H\n  1 1 0.0 0.0 0.0\n  2 1 0.0 0.0 0.75"}},
    "Hamiltonian": {"DFTB": {"SCC": True, "MaxSCCIterations": 100, "SCCTolerance": 1e-5,
        "_raw_1": 'SlaterKosterFiles = Type2FileNames {\n  Prefix = "/opt/skf/mio-1-1/"\n  Separator = "-"\n  Suffix = ".skf"\n}',
        "_raw_2": 'MaxAngularMomentum {\n  H = "s"\n}'}},
    "Analysis": {"CalculateForces": True},
})
node = engine.submit(CalculationFactory("dftbplus"), code=orm.load_code("dftb+@localhost"),
                     parameters=parameters, use_remote_skf_path=orm.Bool(True))
```

Then watch it with `verdi process list -a` and read the result with
`verdi calcjob res <PK>`.

## Where to go next

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} {octicon}`rocket;1.5em;sd-mr-1` Getting started
:link: getting-started/index
:link-type: doc

Install the plugin, register the DFTB+ code, get the right Slater–Koster files,
and run your first calculation from a fresh profile.
:::

:::{grid-item-card} {octicon}`mortar-board;1.5em;sd-mr-1` Tutorials
:link: tutorials/index
:link-type: doc

Sequential, runnable lessons: single-point energy, geometry relaxation, band
structure, submission and monitoring, high-throughput, and your own WorkChain.
:::

:::{grid-item-card} {octicon}`tools;1.5em;sd-mr-1` How-to guides
:link: how-to/index
:link-type: doc

Short answers to single questions: SKF selection, HPC, restarts, SCC
convergence, querying, exporting structures, and every error the parser emits.
:::

:::{grid-item-card} {octicon}`light-bulb;1.5em;sd-mr-1` Explanation
:link: explanation/index
:link-type: doc

How the plugin works, why the CalcJob/Parser split exists, what provenance is
recorded, and an honest primer on what DFTB can and cannot do.
:::

:::{grid-item-card} {octicon}`file-directory;1.5em;sd-mr-1` Architecture
:link: architecture/index
:link-type: doc

For maintainers: module map, entry points, calculation lifecycle, the full
input/output contract, design decisions, and how to contribute.
:::

:::{grid-item-card} {octicon}`book;1.5em;sd-mr-1` Reference
:link: reference/index
:link-type: doc

The generated API reference, the HSD serialisation rules, the CLI commands and
the exit-code table.
:::

::::

(scope-and-limitations)=

## Scope and limitations

Stated up front, because knowing them changes how you use the plugin.

| The plugin does | The plugin does not |
| --- | --- |
| Serialise a nested dict into `dftb_in.hsd` | Validate DFTB+ settings beyond the top-level block names |
| Copy a ready-made `dftb_in.hsd` verbatim | Generate geometries — you supply them as HSD text or files |
| Stage Slater–Koster and material files | Ship or choose Slater–Koster parameters for you |
| Retrieve eight named output files | Retrieve arbitrary or wildcard filenames |
| Parse energies, Fermi level, SCC status and forces from `detailed.out` | Parse band structures, DOS, charges or dipoles |
| Classify failures into four exit codes | Restart, fix or retry a failed calculation |
| Record full provenance for every input node | Provide any `WorkChain` |

There is no {class}`~aiida.orm.nodes.data.structure.StructureData` support: the
`structure` input is a metadata {class}`~aiida.orm.nodes.data.dict.Dict`, and
geometry travels as HSD text or a `.gen` file. See
[Exporting structures and results](how-to/export-structures.md) for converting
what comes back.

```{toctree}
:hidden:
:caption: Getting started

getting-started/index
```

```{toctree}
:hidden:
:caption: Documentation

tutorials/index
how-to/index
explanation/index
architecture/index
reference/index
```

```{toctree}
:hidden:
:caption: Project

changelog
citation
license
acknowledgements
```
