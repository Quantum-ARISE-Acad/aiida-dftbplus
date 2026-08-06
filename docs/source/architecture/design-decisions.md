# Design decisions

Why the plugin is built this way. Each of these was a choice with a cost, and
several were paid for in failed calculations.

(skf-files-bypass-the-sandbox)=

## SKF files bypass the sandbox

**Decision.** `skf_files` goes on `calcinfo.local_copy_list` as
`(uuid, ".", ".")`, not into the sandbox folder.

**Why.** Anything written into the sandbox is copied twice more by the engine:
once into the working directory, and once into the calculation node's own
repository as a record of its raw input. Measured on a real batch:

| | Full set via sandbox | Minimal folder via `local_copy_list` |
| --- | --- | --- |
| Files per job | 5625 | 4 |
| Data per job | 1.5 GB | 904 kB |
| Six jobs, submit → finished | ~50 min | ~1 min |
| DFTB+ time per job | 0.79 s | 0.79 s |

Both daemon workers sat in uninterruptible disk wait, so `verdi daemon status`
timed out and the batch looked hung. It was not hung; it was copying.

**Cost.** The files are not archived per calculation. Provenance is unaffected —
`skf_files` is a stored input node linked to every calculation that used it — but
the raw-input snapshot in the calculation's own repository no longer contains
them.

**The trap.** The first implementation used `(uuid, None, None)`. It passed the
unit tests and then raised `PluginInternalError: local_copy_list format problem`
at upload, because `presubmit` validates entries with
`validate_list_of_string_tuples`, which rejects `None` even though the copy
itself handles it. Twenty-six calculations died that way. The test now runs the
same validator.

**Why `mat_files` still goes through the sandbox.** It is small, and the sandbox
route preserves the ordering that lets the generated `dftb_in.hsd` win over a
stale one shipped among the material files.

## The input is a dictionary, not a file

**Decision.** The primary input is a nested `Dict`, serialised by `_dict_to_hsd`.

**Why.** A `SinglefileData` is opaque. "Which of my 4000 calculations used
`MaxSCCIterations > 100`?" is a database query with a dictionary and a
file-parsing exercise without one.

**Cost.** A serialiser to maintain, and a dictionary form that cannot express
every HSD construct.

**Mitigation.** The `_raw*` escape hatch: any key starting with `_raw` is written
verbatim, so nothing in DFTB+ is unreachable. `dftb_input` remains available for
inputs produced elsewhere.

## Validation stops at the top level

**Decision.** `DftbParameters` checks that top-level keys are among eleven known
blocks. Nothing deeper.

**Why.** Modelling the full DFTB+ input schema would mean tracking every DFTB+
release, and a validator that lags behind the code rejects valid input — worse
than no validator. The top level catches the expensive mistake (a misspelled
block silently ignored) at negligible cost.

**Cost.** A typo inside a block is only caught by DFTB+, at run time, as exit
code 310.

## Convergence failures are checked before the generic error guard

**Decision.** In `_detect_exit_code`: SCC, then geometry, then `ERROR!`.

**Why.** DFTB+ prints `ERROR!` on the line immediately before
`SCC is NOT converged`. Guard-first would classify every recoverable SCC failure
as a fatal 310, and any workflow keyed on 320 would never fire. Found on a real
batch; regression-tested by name.

**Rule for new signatures.** Specific before generic.

## No results are attached to a failed run

**Decision.** `output_parameters` exists only on exit code 0.

**Why.** Numbers in a database get used. Withholding the energy of an
unconverged SCC cycle keeps "give me all results" honest.

**Cost.** Reading the unconverged value takes an extra line against
`retrieved` — which still holds every file.

## The retrieve list is generous and fixed

**Decision.** Eight named files, no wildcards, whether or not the plugin parses
them.

**Why.** Retrieval happens once; parsing can be repeated for ever. Retrieving
`band.out` and `dftb_pin.hsd` costs kilobytes and means a future parser — or a
user with a Python prompt — can work on calculations that have already run.
Wildcards would make the transferred volume unpredictable.

**Cost.** A new output file requires a code change, and old calculations do not
get it retroactively.

## The parsing logic is pure static methods

**Decision.** `_dict_to_hsd`, `_detect_exit_code` and `_parse_detailed` take
strings and return plain Python.

**Why.** Testability. Most of the suite runs without a profile, a database, or
DFTB+, in seconds. It also makes them usable interactively for debugging an
input.

**Cost.** They are private, so their being useful to users is informal. They are
documented anyway.

## Two switches instead of magic

**Decision.** `use_remote_skf_path` and `fix_output_prefix` are explicit `Bool`
inputs with defaults, not inferred behaviour.

**Why.** Both patch the user's input text. A plugin that rewrites your input
without saying so is a plugin you cannot debug. As inputs they are recorded in
the provenance graph, so "was the prefix rewritten for this calculation?" is
answerable years later.

**Cost.** Two more ports on an already wide interface.

## `withmpi` defaults to False

**Decision.** Serial by default.

**Why.** The common DFTB+ builds (including conda-forge's default) are
OpenMP-threaded, not MPI. Launching one under `mpirun` runs N identical copies
that overwrite each other's output — a failure that looks like corrupted results
rather than an error.

## No StructureData, no WorkChains

**Decision.** Geometry is HSD text or a file; the package ships no workflows.

**Why.** Scope. The plugin does one thing: run DFTB+ once, faithfully, with full
provenance. Structure conversion and error recovery are real features with real
maintenance costs, and both can be built on top without changing the
`CalcJob` — [T6](../tutorials/t6-custom-workchain.md) shows how.

**Cost.** Stated plainly on the [front page](../index.md#scope-and-limitations),
because a user who discovers it after building a campaign has been ill served.
