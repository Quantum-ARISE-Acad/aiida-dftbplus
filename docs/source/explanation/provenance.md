# Provenance

What the plugin records, and how to trace a number back to what produced it.

```{graphviz} ../_static/diagrams/provenance.dot
:caption: The graph one calculation leaves behind. Dashed borders are optional inputs.
:align: center
```

## What is recorded

Every input is a stored, immutable node linked to the calculation with an
`INPUT_CALC` edge; every output is linked back with a `CREATE` edge. For a DFTB+
calculation that means the code, the full parameter dictionary, the Slater–Koster
files if you uploaded them, any material files, your metadata, both switches —
and on the other side the remote folder, the retrieved files and the parsed
results.

Nothing in that graph can be edited afterwards. Stored nodes are immutable, and
a result can always be re-derived from its inputs.

## Trace a result back

```python
from aiida import orm

node = orm.load_node(<PK>)

node.inputs.code.full_label                       # 'dftb+@localhost'
node.inputs.parameters.get_dict()                 # the exact settings
node.inputs.structure.get_dict()                  # your metadata
node.get_options()                                # walltime, resources, parser
node.exit_status, node.exit_message
```

```shell
verdi process show <PK>
verdi node graph generate <PK>       # a PDF of the graph above, for your PK
```

## What is *not* recorded

**The Slater–Koster files, when `use_remote_skf_path=True`.** Only the absolute
path inside the input text is kept. If that directory changes or disappears, the
calculation is no longer reproducible from the database alone. This is the price
of not copying gigabytes per job, and it is the reason to record the set's name
in `structure`:

```python
inputs["structure"] = orm.Dict({"formula": "H2O", "skf_set": "3ob-3-1"})
```

With `skf_files`, the files themselves are a node and this problem disappears.

**The DFTB+ version.** AiiDA records the code node, not the binary's version
string. If the executable at that path is upgraded, old calculations still point
at the same `InstalledCode`. Register a new code per version
(`dftb+-24.1@cluster`) if that matters to you — the version banner is also in
`dftb.out`, which is retrieved.

**Anything you did outside AiiDA.** A geometry you tweaked by hand before pasting
it into the script is recorded as the text you pasted, with no history behind it.

## Why the SKF folder is a node worth having

`skf_files` is stored once and linked to every calculation that used it, so:

```python
query = orm.QueryBuilder()
query.append(orm.FolderData, filters={"label": "skf_mio-1-1_H-O"}, tag="skf")
query.append(CalculationFactory("dftbplus"), with_incoming="skf", project=["id"])
```

answers "which calculations used exactly these parameters?" — a question that is
otherwise unanswerable once a shared directory has been reorganised.

The files are *not* duplicated per calculation. They go on the engine's
`local_copy_list`, which copies them into the working directory without staging
them through the sandbox, and therefore without archiving a copy in every
calculation's own repository. Provenance lives on the shared input node.

## Sharing a campaign

```shell
verdi archive create campaign.aiida --groups dftb/screening-2026-08
```

The archive is self-contained — nodes, files, links — and imports into any AiiDA
profile:

```shell
verdi archive import campaign.aiida
```

That is the right artefact to attach to a paper: not a table of energies, but
the inputs that produce them.

## Caching

AiiDA can skip a calculation whose inputs exactly match a previous one:

```shell
verdi config set caching.default_enabled True
```

The match is on a hash of all input nodes. Two consequences specific to this
plugin:

- With `skf_files`, the files are part of the hash, so a different parameter set
  is correctly seen as a different calculation.
- With `use_remote_skf_path=True`, the hash covers only the *path string*. If the
  contents of that directory changed, the cache will happily reuse a result
  computed with the old files. Do not enable caching in that mode unless the
  directory is genuinely immutable.
