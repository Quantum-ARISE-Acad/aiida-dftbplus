# The data model

Which AiiDA node types this plugin uses, what each carries, and — just as
important — which it does not use.

## Nodes that go in

```{list-table}
:header-rows: 1
:widths: 22 22 56

* - Port
  - Node type
  - What it carries
* - `code`
  - `InstalledCode`
  - Which executable on which computer. Required.
* - `parameters`
  - `Dict` / `DftbParameters`
  - The whole DFTB+ input as a nested dictionary. Queryable to any depth.
* - `dftb_input`
  - `SinglefileData`
  - A ready-made `dftb_in.hsd`, opaque. Alternative to `parameters`.
* - `skf_files`
  - `FolderData`
  - Slater–Koster files, uploaded with the job.
* - `mat_files`
  - `FolderData`
  - Any other input file: `charges.bin`, `geometry.gen`, ...
* - `structure`
  - `Dict`
  - **Metadata only.** Never reaches DFTB+.
* - `use_remote_skf_path`
  - `Bool`
  - Upload the SKF files, or trust the path in the input.
* - `fix_output_prefix`
  - `Bool`
  - Rewrite `OutputPrefix = "./"`, default `True`.
```

## Nodes that come out

```{list-table}
:header-rows: 1
:widths: 24 20 56

* - Output
  - Node type
  - What it carries
* - `remote_folder`
  - `RemoteData`
  - A pointer to the working directory on the computer. Not permanent — scratch gets cleaned.
* - `retrieved`
  - `FolderData`
  - Every retrieved file, in the database, permanently.
* - `output_parameters`
  - `Dict`
  - The parsed scalars. Only on exit code 0.
```

`remote_folder` and `retrieved` are created by `CalcJob` itself, not by this
plugin; `output_parameters` is the plugin's only output declaration.

## `DftbParameters` versus a plain `Dict`

`DftbParameters` subclasses `Dict` and adds two things:

- **Validation on construction.** Top-level keys must be known HSD blocks
  (`Analysis`, `Driver`, `ElectronDynamics`, `ExcitedState`, `Geometry`,
  `Hamiltonian`, `Options`, `Parallel`, `ParserOptions`, `Reks`, `Transport`)
  or start with `_`. A typo raises immediately instead of failing on the remote
  machine.
- **`get_hsd()`**, which renders the node as the file it would produce.

The calculation accepts any `Dict`, so `DftbParameters` is optional. Use it: the
validation costs nothing and catches the expensive class of mistake.

The validation stops at the top level on purpose. Modelling the whole DFTB+
input schema would mean tracking every DFTB+ release, and a plugin that lags
behind its code is worse than one that does not pretend to validate.

## What "queryable" means here

Because the input is a `Dict`, every setting is a database attribute:

```python
QueryBuilder().append(DftbParameters, filters={
    "attributes.Hamiltonian.DFTB.MaxSCCIterations": {">": 100},
})
```

With `dftb_input` (a `SinglefileData`) the same question requires opening and
parsing a file per calculation. That is the whole argument for the dictionary
form.

## The metadata escape hatches

Two places to record things that are not DFTB+ settings:

- **`structure`** — a `Dict` input port, never written to the file. Formula,
  source directory, parameter-set name, database id. It is a proper input node,
  so it is queryable and linked.
- **Keys starting with `_`** inside `parameters` — skipped by the serialiser.
  Handy for provenance kept alongside the settings, e.g. `_provenance`.
  (`_raw*` keys are the exception: they *are* written, verbatim.)

## What is deliberately missing

**No `StructureData`.** Geometry travels as HSD text or a `.gen` file, and comes
back as a file in `retrieved`. This means no automatic CIF export, no structure
deduplication, and no direct interoperability with structure-based plugins. See
[Export structures](../how-to/export-structures.md) for the conversion.

**No `BandsData`, `TrajectoryData`, `ArrayData`.** `band.out` and the geometry
files are retrieved unparsed. Forces are stored as a plain list inside
`output_parameters` rather than as an `ArrayData`, which is fine for a handful
of atoms and would not be for a molecular-dynamics trajectory.

**No `RemoteData` restart path.** Restarting reads from `retrieved`, not from
the remote working directory — see [Restart](../how-to/restart.md).

These are consequences of the plugin's scope: one calculation in, one
calculation out. Adding them is a real extension, not a configuration switch.
