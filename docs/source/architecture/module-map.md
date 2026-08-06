# Module map

Five modules, about 700 lines. What each owns, and — the part that keeps the
package small — what each must never do.

```{graphviz} ../_static/diagrams/modules.dot
:caption: Module dependencies. calculations.py imports nothing from the rest of the package.
:align: center
```

## `calculations.py`

**Owns:** the `CalcJob`. Input specification, HSD generation, file staging, the
retrieve list, the exit-code registry.

| Object | Role |
| --- | --- |
| `DftbPlusCalculation` | The `CalcJob`. Entry point `aiida.calculations:dftbplus`. |
| `validate_inputs` | Rejects "neither `parameters` nor `dftb_input`" and "both", before submission. |
| `_dict_to_hsd` | Serialises a nested dict to HSD text. The heart of the plugin. |
| `_patch_skf_paths` | Rewrites an absolute Slater–Koster prefix to `./`. |
| `_fix_output_prefix` | Rewrites `OutputPrefix = "./"` to `"geom.out"`. |

**Must never:** import from any other module of this package (it is the root of
the dependency graph); talk to the scheduler, transport or database; mutate an
input node; validate DFTB+ settings beyond the block names.

## `parsers.py`

**Owns:** turning retrieved files into an exit code and one output node.

| Object | Role |
| --- | --- |
| `DftbPlusParser` | The `Parser`. Entry point `aiida.parsers:dftbplus`. |
| `_detect_exit_code` | Pure function: two strings in, an exit code out. |
| `_parse_detailed` | Pure function: `detailed.out` text in, scalars out. |
| `_map_failure` | Translates a detection integer into a registered exit code, and logs at the right severity. |
| `HARTREE_TO_EV`, `BOHR_TO_ANG`, `HA_BOHR_TO_EV_ANG` | CODATA 2018 conversions. |

It imports the calculation class through `CalculationFactory("dftbplus")`, not
by a direct import — the entry-point registry stays the single source of truth,
and the import cycle never forms.

**Must never:** raise on a failed calculation (it returns exit codes); attach
results from a run that failed; read anything not in `retrieve_list`.

## `data/__init__.py`

**Owns:** the validated parameter node.

| Object | Role |
| --- | --- |
| `DftbParameters` | `Dict` subclass with a voluptuous schema. Entry point `aiida.data:dftbplus`. |
| `hsd_block_name` | The validator for one top-level key. |
| `KNOWN_TOP_LEVEL_BLOCKS` | The eleven blocks a `dftb_in.hsd` may contain. |

Depends on `calculations.py` for `_dict_to_hsd`, so that `get_hsd()` renders
exactly what the calculation would write. One implementation, two callers.

**Must never:** validate deeper than the top level — that would mean tracking
every DFTB+ release.

## `cli.py`

**Owns:** the `verdi data dftbplus` command group.

| Command | Role |
| --- | --- |
| `list` | Every `DftbParameters` node. |
| `export` | A node as plain text. |
| `hsd` | A node as the `dftb_in.hsd` it produces. |

Loads the data class through `DataFactory("dftbplus")` at call time, so
importing the CLI does not require a profile.

**Must never:** modify nodes. It is a read-only view.

## `helpers.py`

**Owns:** test and example convenience — a localhost computer and a code found
on `PATH`.

| Function | Role |
| --- | --- |
| `get_computer` | Load or create `localhost-test` with a temporary work directory. |
| `get_code` | Load or create the `dftb+` code on it. |
| `get_path_to_executable` | `shutil.which`, with a useful error. |

**Must never:** be used in production scripts. It creates computers with
temporary work directories, which is right for tests and wrong for real work.

## Files outside `src/`

| Path | Role |
| --- | --- |
| `tests/test_calculations.py` | Three layers: pure helpers, `prepare_for_submission` in a sandbox, one end-to-end run. |
| `tests/test_cli.py` | The `verdi data dftbplus` commands. |
| `conftest.py` | AiiDA fixtures — a throwaway sqlite, broker-less profile per test. |
| `examples/example_01.py` | A runnable H₂ submission using `helpers`. |
| `docs/diagrams/generate.py` | Regenerates the five Graphviz diagrams. |
| `.github/workflows/` | `ci.yml` (gates), `release.yml` (publish), `codeql.yml`, `docs.yml`. |

## The shape of the dependency graph

`calculations.py` is the root: everything else may depend on it, it depends on
nothing internal. `parsers.py` and `data/` sit above it, `cli.py` above `data/`,
`helpers.py` off to the side. There are no cycles and no clever imports — which
is why the whole package can be read in an afternoon.
