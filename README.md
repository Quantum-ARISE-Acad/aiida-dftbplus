[![Build Status][ci-badge]][ci-link]
[![Coverage Status][cov-badge]][cov-link]
[![Docs status][docs-badge]][docs-link]
[![PyPI version][pypi-badge]][pypi-link]

# aiida-dftbplus

Run [DFTB+](https://dftbplus.org/) from [AiiDA](https://www.aiida.net/): the
plugin writes `dftb_in.hsd`, submits the job, brings every output file back and
stores the input parameters as queryable database attributes.

One calculation in, one calculation out — no workflows, no error recovery.

## Install

```shell
pip install aiida-dftbplus
verdi quicksetup          # if you do not have a profile yet
```

DFTB+ itself comes separately (e.g. `conda install -c conda-forge dftbplus`).
Register it once:

```shell
verdi code create core.code.installed \
    --label dftb+ --computer localhost \
    --default-calc-job-plugin dftbplus \
    --filepath-executable $(which dftb+)
```

## Run something

```shell
verdi daemon start
cd examples
./example_01.py --code dftb+@localhost --skf-dir /path/to/skf/
```

## Describe the input

Write the HSD as a nested dictionary — every setting stays queryable:

```python
from aiida import engine, orm
from aiida.plugins import CalculationFactory, DataFactory

DftbParameters = DataFactory("dftbplus")

parameters = DftbParameters({
    "Geometry": {"GenFormat": {"_raw": open("geometry.gen").read()}},
    "Hamiltonian": {"DFTB": {
        "SCC": True,
        "MaxSCCIterations": 100,
        "SCCTolerance": 1e-5,
        "_raw_1": 'SlaterKosterFiles = Type2FileNames {\n'
                  '  Prefix = "/opt/skf/mio-1-1/"\n'
                  '  Separator = "-"\n  Suffix = ".skf"\n}',
    }},
    "Analysis": {"CalculateForces": True},
})

engine.submit(CalculationFactory("dftbplus"), code=code, parameters=parameters)
```

Anything the dictionary form does not cover goes through verbatim under a
`_raw*` key, so nothing in DFTB+ is out of reach. Dictionaries are validated
before submission — `print(DftbParameters.schema.schema)` lists the blocks.

Already have a file? Hand it over instead:

```python
inputs["dftb_input"] = DataFactory("core.singlefile")(file="dftb_in.hsd")
```

Exactly one of `parameters` or `dftb_input` is required.

## Slater-Koster files

Two options, and the choice matters for speed:

* `use_remote_skf_path=True` — the files already sit on the machine, keep the
  absolute path in the HSD and upload nothing. Best for a full parameter set.
* `skf_files` (a `FolderData`) — ship the files with the job, but **only the
  pairs the run reads**. A full set is copied into every working directory and
  turns a one-second job into a several-minute one; a two-element material needs
  four files:

  ```python
  skf_files = orm.FolderData()
  for name in (f"{a}-{b}.skf" for a in ["O", "S"] for b in ["O", "S"]):
      skf_files.put_object_from_file(str(skf_dir / name), name)
  ```

## Get the results

```shell
verdi process list -a
verdi calcjob res <PK>        # parsed scalars: energies, Fermi level, forces
verdi calcjob outputls <PK>   # every retrieved file
verdi process report <PK>     # why it failed, if it did
```

`output_parameters` carries `total_energy_H`, `total_energy_eV`,
`fermi_energy_eV`, `scc_converged`, `n_scc_iterations`, `forces_eV_Ang` and
`max_force_eV_Ang`. Failures come back as exit codes: **300** output missing,
**310** DFTB+ error, **320** SCC not converged, **330** geometry not converged.

Inspect the stored input nodes with the bundled `verdi` commands:

```shell
verdi data dftbplus list
verdi data dftbplus hsd <PK>    # render the node as the dftb_in.hsd it produces
```

## Documentation

Full input reference and developer guide:
[aiida-dftbplus.readthedocs.io](http://aiida-dftbplus.readthedocs.io/).

## License

MIT — see [LICENSE](LICENSE).

## Contact

sitouamu510@gmail.com

[ci-badge]: https://github.com/Quantum-ARISE-Acad/aiida-dftbplus/workflows/ci/badge.svg?branch=main
[ci-link]: https://github.com/Quantum-ARISE-Acad/aiida-dftbplus/actions
[cov-badge]: https://coveralls.io/repos/github/Quantum-ARISE-Acad/aiida-dftbplus/badge.svg?branch=main
[cov-link]: https://coveralls.io/github/Quantum-ARISE-Acad/aiida-dftbplus?branch=main
[docs-badge]: https://readthedocs.org/projects/aiida-dftbplus/badge
[docs-link]: http://aiida-dftbplus.readthedocs.io/
[pypi-badge]: https://badge.fury.io/py/aiida-dftbplus.svg
[pypi-link]: https://badge.fury.io/py/aiida-dftbplus
