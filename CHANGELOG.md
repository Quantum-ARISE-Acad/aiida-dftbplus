# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing has been published to PyPI yet; the current version, `0.1.0a0`, is a
pre-release that `pip` installs only with `--pre`. The first published release
will be `0.1.0`.

### Added

- `DftbPlusCalculation`, a `CalcJob` wrapping one DFTB+ execution: HSD
  generation from a nested dictionary, Slater–Koster and material file staging,
  and a fixed eight-file retrieve list.
- `DftbPlusParser`, classifying the run into four exit codes and extracting
  energies, Fermi level, SCC status and forces from `detailed.out`.
- `DftbParameters`, a validated `Dict` subclass checking the top-level HSD block
  names, with `get_hsd()` to render the input as the file it produces.
- `verdi data dftbplus` command group: `list`, `export`, `hsd`.
- `use_remote_skf_path` and `fix_output_prefix` input switches.
- A complete documentation site: getting started, six tutorials, eight how-to
  guides, explanation and architecture sections, and a generated API reference.
- CI/CD: lint, SAST, dependency review, build, tests on Python 3.9–3.12, an
  integration job running a real DFTB+ from conda-forge, and a docs build with
  warnings treated as errors. Publishing uses PyPI Trusted Publishing.

### Fixed

- **Slater–Koster staging no longer goes through the sandbox.** The `skf_files`
  node is passed on `calcinfo.local_copy_list` as `(uuid, ".", ".")`, so the
  engine copies it once into the working directory instead of three times. A
  batch that had been shipping 5625 files (1.5 GB) per 0.79-second calculation
  went from ~50 minutes to ~1 minute.
- `local_copy_list` entries are strings, never `None`: `presubmit` validates
  them with `validate_list_of_string_tuples`, which rejects `None` even though
  the copy itself tolerates it. A regression test now runs the same validator.
- Convergence signatures are checked before the generic `ERROR!` guard in
  `_detect_exit_code`, because DFTB+ prints `ERROR!` on the line immediately
  before `SCC is NOT converged`. Without this, every recoverable SCC failure was
  reported as a fatal 310.
- The package could not be built at all: `authors = [{..., email = "-"}]` in
  `pyproject.toml` made hatchling raise `InvalidHeaderDefect` during metadata
  generation.
- `hatch test` was unresolvable: the test dependencies moved into a `tests`
  extra with open upper bounds, so `hatch test` and `pip install -e .[tests]`
  install one shared set.
- The docs build is green on a clean tree with `-nW`, after fixing a docstring
  that reStructuredText read as an unterminated emphasis marker and adding
  nitpick exemptions for AiiDA's private module paths.
- The test fixtures use `aiida.tools.pytest_fixtures` (the deprecated
  `aiida.manage.tests.pytest_fixtures` was removed in aiida-core v3), so the
  suite needs neither PostgreSQL nor RabbitMQ.

### Known limitations

- No `WorkChain` is shipped; there is no `aiida.workflows` entry point.
- No `StructureData` support: geometry travels as HSD text or a `.gen` file.
- `band.out`, the geometry files, charges and dipole moments are retrieved but
  not parsed.
- `n_scc_iterations` is absent with recent DFTB+ versions, which no longer print
  the line the parser looks for.

See [known parsing gaps](https://quantum-arise-acad.github.io/aiida-dftbplus/reference/exit-codes.html#known-parsing-gaps)
for the current list.
