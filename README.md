[![Build Status][ci-badge]][ci-link]
[![Coverage Status][cov-badge]][cov-link]
[![Docs status][docs-badge]][docs-link]
[![PyPI version][pypi-badge]][pypi-link]

# aiida-dftbplus

AiiDA plugin for [DFTB+](https://dftbplus.org/) calculations.

The plugin submits a DFTB+ run, retrieves every output file it produces, and
records the input parameters in the AiiDA database so they stay queryable. It
covers a single calculation: there are no workflows and no automatic error
recovery.

## Repository contents

* [`.github/`](.github/): [Github Actions](https://github.com/features/actions) configuration
  * [`ci.yml`](.github/workflows/ci.yml): runs tests, checks test coverage and builds documentation at every new commit
  * [`publish-on-pypi.yml`](.github/workflows/publish-on-pypi.yml): automatically deploy git tags to PyPI - just generate a [PyPI API token](https://pypi.org/help/#apitoken) for your PyPI account and add it to the `pypi_token` secret of your github repository
* [`src/aiida_dftbplus/`](src/aiida_dftbplus/): The main source code of the plugin package
  * [`calculations.py`](src/aiida_dftbplus/calculations.py): The `DftbPlusCalculation` `CalcJob` class — assembles `dftb_in.hsd` and the files the run needs, and defines what is retrieved
  * [`parsers.py`](src/aiida_dftbplus/parsers.py): The `DftbPlusParser` — classifies the run and extracts the scalars from `detailed.out`
  * [`data/`](src/aiida_dftbplus/data/): The `DftbParameters` data class, a validated dictionary of DFTB+ input blocks
  * [`cli.py`](src/aiida_dftbplus/cli.py): Extensions of the `verdi data` command line interface for the `DftbParameters` class
  * [`helpers.py`](src/aiida_dftbplus/helpers.py): Helpers for setting up an AiiDA code for `dftb+` automatically
* [`docs/`](docs/): A documentation template ready for publication on [Read the Docs](http://aiida-dftbplus.readthedocs.io/en/latest/)
* [`examples/`](examples/): An example of how to submit a calculation using this plugin
* [`tests/`](tests/): Tests using the [pytest](https://docs.pytest.org/en/latest/) framework. Most need neither a DFTB+ binary nor an AiiDA profile.
* [`.gitignore`](.gitignore): Telling git which files to ignore
* [`.pre-commit-config.yaml`](.pre-commit-config.yaml): Configuration of [pre-commit hooks](https://pre-commit.com/) that sanitize coding style and check for syntax errors. Enable via `pip install -e .[pre-commit] && pre-commit install`
* [`.readthedocs.yml`](.readthedocs.yml): Configuration of documentation build for [Read the Docs](https://readthedocs.org/)
* [`LICENSE`](LICENSE): License for your plugin
* [`README.md`](README.md): This file
* [`conftest.py`](conftest.py): Configuration of fixtures for [pytest](https://docs.pytest.org/en/latest/)
* [`pyproject.toml`](pyproject.toml): Python package metadata for registration on [PyPI](https://pypi.org/) and the [AiiDA plugin registry](https://aiidateam.github.io/aiida-registry/) (including entry points)

## Features

 * Describe the DFTB+ input as a Python dictionary that mirrors the HSD block
   structure, and let the plugin write `dftb_in.hsd` for you:
   ```python
   DftbParameters = DataFactory('dftbplus')
   inputs['parameters'] = DftbParameters({
       'Geometry': {'GenFormat': {'_raw': open('geometry.gen').read()}},
       'Hamiltonian': {'DFTB': {
           'SCC': True,
           'MaxSCCIterations': 100,
           'SCCTolerance': 1e-5,
       }},
       'Analysis': {'CalculateForces': True},
   })
   ```
   Every setting is then a queryable database attribute rather than text inside
   an opaque file.

 * Any block the dictionary form does not cover can be passed through verbatim
   under a `_raw*` key, so no DFTB+ feature is out of reach:
   ```python
   'Hamiltonian': {'DFTB': {
       'SCC': True,
       '_raw_1': 'SlaterKosterFiles = Type2FileNames {\n'
                 '  Prefix = "/opt/skf/mio-1-1/"\n'
                 '  Separator = "-"\n  Suffix = ".skf"\n}',
   }}
   ```

 * Or skip the dictionary entirely and hand over a file you already have:
   ```python
   SinglefileData = DataFactory('core.singlefile')
   inputs['dftb_input'] = SinglefileData(file='/path/to/dftb_in.hsd')
   ```
   Exactly one of `parameters` or `dftb_input` is required; supplying neither
   (or both) fails at submission rather than on the remote machine.

 * `DftbParameters` dictionaries are validated using
   [voluptuous](https://github.com/alecthomas/voluptuous), so a mistyped block
   name is caught before the job is submitted. Find out about supported blocks:
   ```python
   DftbParameters = DataFactory('dftbplus')
   print(DftbParameters.schema.schema)
   ```

 * Slater-Koster files can travel with the job (`skf_files`, a `FolderData`
   stored once and reused) or stay on the remote machine
   (`use_remote_skf_path=True`, which keeps the absolute path already written
   in the HSD and uploads nothing — the right choice for a full parameter set
   of several thousand files).

   When you do ship them, ship only the pairs the run reads. A `FolderData`
   holding a whole parameter set is copied into the working directory of every
   calculation, so a full set turns a one-second job into a several-minute one;
   a two-element material needs four files. Build the folder from the elements
   in the input:
   ```python
   elements = ['O', 'S']
   skf_files = FolderData()
   for name in (f'{a}-{b}.skf' for a in elements for b in elements):
       skf_files.put_object_from_file(str(skf_dir / name), name)
   ```

### Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `code` | `AbstractCode` | yes | The registered DFTB+ executable |
| `parameters` | `Dict` | one of the two | DFTB+ input blocks as a nested dictionary |
| `dftb_input` | `SinglefileData` | one of the two | A ready-made `dftb_in.hsd` |
| `skf_files` | `FolderData` | no | The `*.skf` Slater-Koster files |
| `mat_files` | `FolderData` | no | Other files the run needs (`geometry.gen`, `charges.bin`, ...) |
| `structure` | `Dict` | no | Metadata (`formula`, `source_dir`) kept for provenance |
| `use_remote_skf_path` | `Bool` | no (`False`) | Keep the absolute SKF path and upload no SKF file |
| `fix_output_prefix` | `Bool` | no (`True`) | Rewrite `OutputPrefix = './'` to a real filename |

### Outputs

`retrieved` (`FolderData`) always holds everything DFTB+ wrote that the plugin
asked for: `dftb.out`, `dftb.err`, `detailed.out`, `band.out`, `geom.out.gen`,
`geom.out.xyz`, `charges.bin` and `dftb_pin.hsd`.

`output_parameters` (`Dict`) holds the scalars read from `detailed.out`:
`total_energy_H`, `total_energy_eV`, `fermi_energy_eV`, `scc_converged`,
`n_scc_iterations`, `forces_eV_Ang` and `max_force_eV_Ang`.

### Exit codes

| Code | Name | Meaning |
|---|---|---|
| 300 | `ERROR_MISSING_OUTPUT` | `dftb.out` or `detailed.out` was not retrieved |
| 310 | `ERROR_DFTB_FAILED` | DFTB+ reported a fatal error in `dftb.out` |
| 320 | `ERROR_SCC_NOT_CONVERGED` | The SCC cycle did not converge |
| 330 | `ERROR_GEOMETRY_NOT_CONVERGED` | Relaxation did not converge within `MaxSteps` |

## Installation

```shell
pip install aiida-dftbplus
verdi quicksetup  # better to set up a new profile
verdi plugin list aiida.calculations  # should now show your calclulation plugins
```

DFTB+ itself is not installed by this package. Install it separately (for
example `conda install -c conda-forge dftbplus`) and register it:

```shell
verdi code create core.code.installed \
    --label dftb+ --computer localhost \
    --default-calc-job-plugin dftbplus \
    --filepath-executable $(which dftb+)
```

## Usage

A quick demo of how to submit a calculation:
```shell
verdi daemon start     # make sure the daemon is running
cd examples
./example_01.py --code dftb+@localhost --skf-dir /path/to/skf/
verdi process list -a  # check record of calculation
```

Inspect the result:
```shell
verdi calcjob outputls <PK>   # every retrieved file
verdi calcjob res <PK>        # the parsed output_parameters
verdi process report <PK>     # why it failed, if it did
```

The plugin also includes verdi commands to inspect its data types:
```shell
verdi data dftbplus list
verdi data dftbplus export <PK>
verdi data dftbplus hsd <PK>    # render the node as the dftb_in.hsd it produces
```

## Development

```shell
git clone https://github.com/Quantum-ARISE-Acad/aiida-dftbplus .
cd aiida-dftbplus
pip install --upgrade pip
pip install -e .[pre-commit,testing]  # install extra dependencies
pre-commit install  # install pre-commit hooks
pytest -v  # discover and run all tests
```

Most tests are pure-function tests of the HSD serialiser, the exit-code
detection and the `detailed.out` parsing, and need neither an AiiDA profile nor
a DFTB+ binary. The single end-to-end test is skipped unless `dftb+` is on the
PATH.

See the [developer guide](http://aiida-dftbplus.readthedocs.io/en/latest/developer_guide/index.html) for more information.

## License

MIT
## Contact

sitouamu510@gmail.com


[ci-badge]: https://github.com/ShellRuner/aiida-dftbplus/workflows/ci/badge.svg?branch=master
[ci-link]: https://github.com/ShellRuner/aiida-dftbplus/actions
[cov-badge]: https://coveralls.io/repos/github/ShellRuner/aiida-dftbplus/badge.svg?branch=master
[cov-link]: https://coveralls.io/github/ShellRuner/aiida-dftbplus?branch=master
[docs-badge]: https://readthedocs.org/projects/aiida-dftbplus/badge
[docs-link]: http://aiida-dftbplus.readthedocs.io/
[pypi-badge]: https://badge.fury.io/py/aiida-dftbplus.svg
[pypi-link]: https://badge.fury.io/py/aiida-dftbplus
