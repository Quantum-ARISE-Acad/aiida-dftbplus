# Input/output contract

Every port, its type, whether it is required, and what it does. The
authoritative version is the process spec itself — `verdi plugin list
aiida.calculations dftbplus`, or the [API reference](../reference/api/index.md).

```{graphviz} ../_static/diagrams/io_contract.dot
:caption: Dashed borders mark optional ports.
:align: center
```

## Inputs

```{list-table}
:header-rows: 1
:widths: 20 18 10 52

* - Port
  - Type
  - Required
  - Notes
* - `code`
  - `AbstractCode`
  - yes
  - Inherited from `CalcJob`. Usually an `InstalledCode`.
* - `parameters`
  - `Dict`
  - one of two
  - Nested dict mirroring the HSD blocks. `DftbParameters` is a `Dict`, so it fits here.
* - `dftb_input`
  - `SinglefileData`
  - one of two
  - A ready-made `dftb_in.hsd`, copied verbatim.
* - `skf_files`
  - `FolderData`
  - no
  - Slater–Koster files. Goes on `local_copy_list`, not through the sandbox.
* - `mat_files`
  - `FolderData`
  - no
  - Any other input file. A `dftb_in.hsd` inside it is skipped.
* - `structure`
  - `Dict`
  - no
  - Metadata only; never reaches DFTB+. Suggested keys: `formula`, `source_dir`.
* - `use_remote_skf_path`
  - `Bool`
  - no (default `False`)
  - `True`: keep the absolute prefix, upload nothing.
* - `fix_output_prefix`
  - `Bool`
  - no (default `True`)
  - Rewrite `OutputPrefix = "./"` to `"geom.out"`.
* - `metadata.options.*`
  - various
  - no
  - Resources, walltime, `withmpi`, `parser_name`, environment variables.
```

`validate_inputs` enforces the "exactly one of `parameters` / `dftb_input`" rule
at the namespace level, before submission:

```text
One of 'parameters' or 'dftb_input' is required.
Provide either 'parameters' or 'dftb_input', not both.
```

### Option defaults set by this plugin

```python
parser_name           = "dftbplus"
resources             = {"num_machines": 1, "num_mpiprocs_per_machine": 1}
max_wallclock_seconds = 7200
withmpi               = False
```

`withmpi=False` is deliberate: the common DFTB+ builds are OpenMP-threaded, and
launching a serial binary under `mpirun` runs N copies of the same calculation.

### Interaction between `skf_files` and `use_remote_skf_path`

```{list-table}
:header-rows: 1
:widths: 20 22 26 32

* - `skf_files`
  - `use_remote_skf_path`
  - Uploaded
  - Prefix in `dftb_in.hsd`
* - given
  - `False` (default)
  - the whole folder
  - rewritten to `"./"`
* - given
  - `True`
  - nothing
  - left as written
* - absent
  - either
  - nothing
  - left as written
```

Row two is a legitimate combination: the node stays linked for provenance while
the files on the remote machine are the ones actually read.

## Outputs

```{list-table}
:header-rows: 1
:widths: 22 20 12 46

* - Output
  - Type
  - Always
  - Notes
* - `remote_folder`
  - `RemoteData`
  - yes
  - Created by `CalcJob`. Points at the working directory; not permanent.
* - `retrieved`
  - `FolderData`
  - yes
  - Everything in the retrieve list that existed, plus the scheduler files.
* - `output_parameters`
  - `Dict`
  - no
  - Attached only on exit code 0.
```

### Keys inside `output_parameters`

```{list-table}
:header-rows: 1
:widths: 26 16 58

* - Key
  - Type
  - Present when
* - `total_energy_H`
  - float
  - `detailed.out` has a `Total energy:` line
* - `total_energy_eV`
  - float
  - same, converted with CODATA 2018
* - `fermi_energy_eV`
  - float
  - DFTB+ printed a Fermi level (usually periodic systems)
* - `scc_converged`
  - bool
  - always
* - `n_scc_iterations`
  - int
  - the DFTB+ version printed an `N SCC iter` line — recent versions do not
* - `forces_eV_Ang`
  - list of [Fx, Fy, Fz]
  - forces were requested
* - `max_force_eV_Ang`
  - float
  - forces were requested; the largest **magnitude**, not component
```

## Retrieve list

```text
dftb.out       dftb.err       detailed.out   band.out
geom.out.gen   geom.out.xyz   charges.bin    dftb_pin.hsd
```

Fixed, with no wildcards. Names missing from the working directory are simply
absent from `retrieved` — not an error. Adding a name affects only calculations
submitted afterwards.

## Exit codes

| Code | Name | Meaning |
| --- | --- | --- |
| 0 | — | No known failure signature |
| 300 | `ERROR_MISSING_OUTPUT` | `dftb.out` or `detailed.out` missing |
| 310 | `ERROR_DFTB_FAILED` | Fatal DFTB+ error, or empty stdout |
| 320 | `ERROR_SCC_NOT_CONVERGED` | SCC cycle did not converge |
| 330 | `ERROR_GEOMETRY_NOT_CONVERGED` | Relaxation ran out of steps |

Reference them by name, never by number:

```python
DftbPlusCalculation.exit_codes.ERROR_SCC_NOT_CONVERGED.status
```

## Stability

The ports, the exit-code names and the four entry-point names are the plugin's
public API; changing them breaks user code and, for entry points, existing
databases. The private helpers (`_dict_to_hsd`, `_detect_exit_code`,
`_parse_detailed`) are documented but not stable — they may change shape between
releases.
