# Prerequisites

`aiida-dftbplus` is a thin layer. It does not contain DFTB+, it does not contain
parameters, and it does not set up AiiDA. **Four things must exist before a
calculation can run**, and the plugin will not obtain any of them for you.

| # | What | How you know it is there |
| --- | --- | --- |
| 1 | A working AiiDA profile | `verdi status` is green |
| 2 | A configured `Computer` | `verdi computer test <name>` passes |
| 3 | A DFTB+ binary on that computer | `dftb+ --version` prints a version |
| 4 | Slater–Koster (`.skf`) files for **every element pair** in your system | the files exist and the set covers your elements |

Items 1 and 2 are AiiDA's own setup, documented in the
[AiiDA installation guide](https://aiida.readthedocs.io/projects/aiida-core/en/latest/installation/index.html).
Items 3 and 4 are the DFTB+ side, covered here and on the
[SKF page](skf-parameter-sets.md).

## 1. An AiiDA profile

A profile is the database and file repository AiiDA stores everything in. If you
have none:

```shell
verdi presto
```

`verdi presto` (aiida-core ≥ 2.6) creates a profile backed by SQLite, with no
PostgreSQL to install, **and sets up and configures `localhost` as a computer
for you** — which covers item 2 as well. It uses RabbitMQ if it finds one
running and otherwise creates a **broker-less** profile.

:::{important}
A broker-less profile cannot run the daemon, and therefore cannot use
`engine.submit()` — only `engine.run()`, which blocks your terminal until the
calculation finishes. That is fine for the first tutorials and hopeless for a
high-throughput campaign.

Check which you have:

```shell
verdi profile show | grep -i broker
verdi status
```

To get a broker, install RabbitMQ (`conda install -c conda-forge rabbitmq-server`,
then `rabbitmq-server -detached`) and create the profile again, or migrate an
existing one with `verdi profile configure-rabbitmq`.
:::

For production work with many calculations, use a PostgreSQL profile
(`verdi quicksetup` or `verdi profile setup core.psql_dos`): SQLite serialises
writes and will bottleneck a busy daemon.

## 2. A configured computer

Where the jobs run. For a first run, localhost:

```shell
verdi computer setup --label localhost --hostname localhost \
    --transport core.local --scheduler core.direct \
    --work-dir /home/$USER/aiida_run --mpiprocs-per-machine 1 \
    --non-interactive
verdi computer configure core.local localhost --safe-interval 0 --non-interactive
verdi computer test localhost
```

`core.direct` means "run it immediately, no queue". For a cluster, use the
scheduler your site runs (`core.slurm`, `core.pbspro`, `core.sge`, ...) and the
`core.ssh` transport — see [Run on a remote machine](../how-to/remote-hpc.md).

## 3. A DFTB+ binary

The plugin runs whatever executable you register; it never installs one.

::::{tab-set}

:::{tab-item} conda-forge (easiest)

```shell
conda install -c conda-forge dftbplus
dftb+ --version
```

Add `dftbplus-tools` for the post-processing utilities (`dp_bands`, `dp_dos`,
`gen2xyz`, ...), which the band-structure tutorial uses. For an MPI build ask
conda for one explicitly, e.g. `conda install -c conda-forge "dftbplus=*=mpi_*"`.
:::

:::{tab-item} From source

Build from <https://github.com/dftbplus/dftbplus> when you need features the
conda build does not carry (transport, ELSI solvers, a specific MPI). Follow the
project's `INSTALL.rst`; the plugin only needs the resulting `dftb+`
executable.
:::

::::

:::{note}
DFTB+ is OpenMP-parallel by default. A serial build still spawns as many threads
as you have cores unless you tell it otherwise, which will oversubscribe a node
running many jobs at once. Set the thread count per calculation:

```python
builder.metadata.options.environment_variables = {"OMP_NUM_THREADS": "1"}
```
:::

## 4. Slater–Koster parameter files

**This is the part people get wrong.** DFTB+ is not a first-principles code: the
Hamiltonian and overlap matrix elements are tabulated in advance, per element
*pair*, in `.skf` files. Without a set that covers every pair of elements in
your structure, DFTB+ cannot start — and a set that covers the elements but was
parameterised for a different purpose will run happily and give you numbers that
are wrong for your problem.

Getting them, choosing them, and pointing the plugin at them is its own page:
**[Slater–Koster parameter sets](skf-parameter-sets.md)**.

## What you do *not* need

- **A `StructureData` node.** This plugin does not use one. Geometry is HSD text
  (a `GenFormat` block) or a `.gen` file shipped in `mat_files`.
- **`pymatgen` or `ASE`.** Neither is a dependency. They are useful for preparing
  geometries and reading results, and the
  [export guide](../how-to/export-structures.md) shows how, but nothing here
  requires them.
- **A `CHANGELOG`-worth of AiiDA experience.** You do need to know what a profile,
  a computer and a code are — the three commands above are enough.

Next: [Installation](installation.md).
