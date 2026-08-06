# Contributing

## Development install

```shell
git clone https://github.com/Quantum-ARISE-Acad/aiida-dftbplus
cd aiida-dftbplus
pip install -e .[tests,pre-commit]
pre-commit install
pytest -v
```

Expect **39 passed** (38 passed and 1 skipped without a `dftb+` binary). The
tests need no database service: the AiiDA fixtures create a throwaway sqlite,
broker-less profile per test.

## Running the gates

Everything CI runs, runnable locally:

```shell
hatch fmt --check          # ruff lint + format
hatch run security:all     # bandit + pip-audit
hatch test --cover         # tests with coverage
hatch run docs:build       # docs, warnings as errors
hatch build                # sdist + wheel
```

`hatch fmt --check` is the same command as the pre-commit hook, so local and CI
verdicts agree. Line length is 120; the rule selection is in `pyproject.toml`.

:::{tip}
For the documentation, an *incremental* build hides autodoc and cross-reference
warnings that CI will fail on. Reproduce what CI sees with:

```shell
hatch run docs:rebuild     # == make -C docs clean-all html
```
:::

## The test suite, in three layers

`tests/test_calculations.py` is organised by what each layer needs:

| Layer | Needs | Covers |
| --- | --- | --- |
| 1 | nothing | `_dict_to_hsd`, `_patch_skf_paths`, `_fix_output_prefix`, `_detect_exit_code`, `_parse_detailed`, `validate_inputs` |
| 2 | an AiiDA profile | `prepare_for_submission` against a `SandboxFolder` |
| 3 | a real `dftb+` | one end-to-end run, skipped if the binary is absent |

Sample DFTB+ input and output live as inline string constants, not fixture
files, so the repository layout does not change when a case is added.

**Put new logic in layer 1 where you can.** A pure function over strings is
testable in microseconds and is why the check-order rule has a regression test
at all.

## Docstring conventions

NumPy style throughout, rendered by napoleon into the
[API reference](../reference/api/index.md):

```python
def thing(argument: str, count: int = 1) -> dict:
    """One-line summary in the imperative.

    Extended description, if the summary is not enough.

    Parameters
    ----------
    argument : str
        What it is.
    count : int, default: 1
        What it does.

    Returns
    -------
    dict
        What comes back.

    Raises
    ------
    ValueError
        When, and why.

    Examples
    --------
    >>> thing("a")
    {'a': 1}

    Notes
    -----
    The reasoning a reader cannot recover from the code.
    """
```

Two rules specific to this project:

- **Nothing in the API reference is hand-written.** If something is missing from
  the rendered site, fix the docstring, not the page.
- **`*` starts emphasis in reStructuredText.** Write ``` ``*.skf`` ``` or "SKF
  (`.skf`) files"; a bare `*.skf` in a docstring or a `help=` string breaks the
  docs build.

## Adding to the parser

Parsing a new quantity from `detailed.out`:

1. Add the extraction to `_parse_detailed`, keyed by unit
   (`dipole_moment_debye`, not `dipole`).
2. Take the **last** occurrence if the quantity can repeat — a geometry
   optimisation writes one block per step.
3. Add a unit test with a real snippet of `detailed.out` as an inline constant.
4. Document the key in [the I/O contract](io-contract.md).
5. Old calculations can be re-parsed: the files are already in `retrieved`.

Recognising a new failure mode:

1. Add the signature to `_detect_exit_code`, **before** the generic `ERROR!`
   guard if it is more specific.
2. Register the exit code in `DftbPlusCalculation.define` with a name and
   message.
3. Map it in `_map_failure`, choosing the log severity deliberately: warning for
   a recoverable physics failure, error for a broken setup.
4. Add a test with output that contains the trap you are avoiding.

Parsing a *new file* (a `BandsData` from `band.out`, say) is a larger change: a
new output port in `define`, the parsing itself, and a decision about whether it
is optional. Discuss it in an issue first.

## Adding an input port

1. `spec.input(...)` in `define`, with `required=False` and a `help` string that
   reads well in `verdi plugin list`.
2. Use it in `prepare_for_submission`.
3. Extend `validate_inputs` if it interacts with existing ports.
4. Test it in layer 2, asserting on the sandbox contents and the `CalcInfo`.
5. Document it in [the I/O contract](io-contract.md) and, if it changes
   behaviour, in [Design decisions](design-decisions.md).

New ports are additive and safe. Renaming or removing one breaks user code.

## Regenerating the diagrams

```shell
python docs/diagrams/generate.py
```

Writes five `.dot` files into `docs/source/_static/diagrams/`, rendered to SVG at
build time. Keep the shared visual language in `docs/diagrams/style.py`: one
colour *and* one shape per category, dashed for optional.

## Pull requests

- One change per pull request.
- Tests for anything with logic in it.
- Documentation in the same PR — prose that contradicts the code is worse than
  no prose.
- CI must be green: `lint`, `sast`, `build`, `test` on Python 3.9–3.12,
  `integration` with a real DFTB+ from conda-forge, and `docs`. The single
  required check is **`ci success`**, which aggregates them.

## Releasing

The full procedure is in
[`.github/RELEASING.md`](https://github.com/Quantum-ARISE-Acad/aiida-dftbplus/blob/main/.github/RELEASING.md).
In short: `hatch version <new>`, push to `main` (which publishes to TestPyPI),
then tag `vX.Y.Z` (which publishes to PyPI via Trusted Publishing). The tag must
match `__version__`; the pipeline refuses to publish otherwise.

## Reporting a bug

Include the plugin version, the aiida-core version, the DFTB+ version from the
top of `dftb.out`, the exit status, and the output of `verdi process report
<PK>`. For a parsing problem, attach the `detailed.out` — it is the input the
parser sees, and a test case can be written from it directly.

<https://github.com/Quantum-ARISE-Acad/aiida-dftbplus/issues>
