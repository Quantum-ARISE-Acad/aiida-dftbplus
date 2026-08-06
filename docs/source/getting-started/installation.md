# Installation

## From PyPI

```shell
pip install aiida-dftbplus
```

This pulls in `aiida-core>=2.5,<3` and `voluptuous`, and nothing else. Python
3.9 or newer is required.

## From source

```shell
git clone https://github.com/Quantum-ARISE-Acad/aiida-dftbplus
cd aiida-dftbplus
pip install .
```

## Development install

Editable, with the test dependencies and the pre-commit hooks:

```shell
git clone https://github.com/Quantum-ARISE-Acad/aiida-dftbplus
cd aiida-dftbplus
pip install -e .[tests,pre-commit]
pre-commit install
pytest -v
```

The test suite needs no database service and no DFTB+ binary: the AiiDA fixtures
create a throwaway SQLite, broker-less profile, and the one end-to-end test
skips itself unless `dftb+` is on `PATH`. Expect **39 passed**, or 38 passed and
1 skipped without the binary.

To build the documentation you are reading:

```shell
pip install -e . --group docs
make -C docs            # strict build: warnings are errors
make -C docs view
```

Graphviz must be installed for the diagrams (`conda install -c conda-forge
graphviz`, or `apt install graphviz`). Set `DOCS_OFFLINE=1` to skip the
intersphinx inventory downloads on a machine with no network.

See [Contributing](../architecture/contributing.md) for the full developer
workflow, and [`.github/RELEASING.md`](https://github.com/Quantum-ARISE-Acad/aiida-dftbplus/blob/main/.github/RELEASING.md)
for how releases are cut.

## Confirm AiiDA sees the plugin

Installation registers four entry points. AiiDA discovers them automatically —
no configuration file to edit:

```shell
verdi plugin list aiida.calculations | grep dftbplus
verdi plugin list aiida.parsers      | grep dftbplus
verdi plugin list aiida.data         | grep dftbplus
```

Each should print `dftbplus`. To see the full input specification of the
calculation:

```shell
verdi plugin list aiida.calculations dftbplus
```

:::{tip}
If the entry points do not appear, the usual cause is that the plugin was
installed into a different environment from the one running `verdi`. Check with
`which verdi` and `pip show aiida-dftbplus`. If they agree and the entry points
are still missing, clear the cache with `reentry scan` (aiida-core < 2) or
simply reinstall the package.
:::

Next: [Registering the DFTB+ code](configure-code.md).
