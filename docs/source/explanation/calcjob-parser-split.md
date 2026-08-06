# Why the CalcJob/Parser split exists

Every AiiDA calculation plugin is two classes. It is worth understanding why,
because the split is what makes the plugin debuggable.

## They run at different times, in different places

| | `DftbPlusCalculation` | `DftbPlusParser` |
| --- | --- | --- |
| Runs | before the job is submitted | after the files come back |
| Where | in the daemon worker, with the sandbox | in the daemon worker, with `retrieved` |
| Input | AiiDA nodes | text files |
| Output | files + a `CalcInfo` | an exit code + output nodes |
| Can it fail usefully? | validation errors, before anything runs | exit codes, after everything ran |
| Re-runnable | no — would mean a new calculation | **yes**, on the stored files |

The last row is the practical payoff.

## The parser can be re-run

`retrieved` is stored in the database, so parsing can be repeated at any time
without re-running DFTB+:

```shell
verdi calcjob res <PK>                 # what was parsed
verdi process report <PK>
```

If a parser bug is fixed, or you add extraction of a quantity that used to be
ignored, every past calculation can be re-parsed from files you already have.
That is only possible because parsing is separate from running, and because the
retrieve list is generous — eight files, not just the one currently parsed.

## Failure means different things on the two sides

**On the calculation side**, failure means "this should not be submitted": no
`parameters` and no `dftb_input`, or both. The validator raises before a single
byte moves, because the alternative is DFTB+ discovering the problem minutes
later on a remote machine — after a queue wait.

**On the parser side**, failure means "the job ran and here is what happened".
It never raises. It returns an exit code, and the outputs stay on the node
either way. Exit code 320 (SCC not converged) is a *result*, not a crash: the
run happened, the physics did not converge, and everything DFTB+ wrote is still
there to look at.

## Why the parser attaches nothing when the run failed

On any non-zero exit code, `output_parameters` is not created. That is
deliberate. Unconverged energies are numbers, and numbers in a database get
used. Leaving them out means a query for results returns only results.

Nothing is lost: `detailed.out` is on the `retrieved` node and can be read,
parsed by hand, or re-parsed by a fixed parser.

## Why the logic sits in static methods

```python
DftbPlusParser._detect_exit_code(stdout, detailed) -> int
DftbPlusParser._parse_detailed(text) -> dict
DftbPlusCalculation._dict_to_hsd(params) -> str
```

Three pure functions: strings in, plain Python out. No profile, no database, no
binary, no engine. Most of the test suite calls them directly, which is why the
tests run in seconds and why the trickiest rule in the plugin — that
`SCC IS NOT CONVERGED` must be checked before `ERROR!` — has a regression test
that takes microseconds.

The same functions are usable interactively, which is the fastest way to debug
an input:

```python
from aiida_dftbplus.calculations import DftbPlusCalculation

print(DftbPlusCalculation._dict_to_hsd(my_dict))
```

They are private (`_`-prefixed) because they are not a stable API for external
code, but they are documented on purpose: they carry the load-bearing logic, and
a maintainer needs to read about them.

## What this means when you extend the plugin

- Parsing a new quantity → touch `_parse_detailed`, add a unit test with a
  sample of `detailed.out`, and re-parse old calculations. No new DFTB+ runs.
- Retrieving a new file → touch `retrieve_list` in `prepare_for_submission`.
  Only affects calculations submitted afterwards.
- Recognising a new failure mode → touch `_detect_exit_code` *and* register the
  exit code in `define`. Mind the check order.

See [Contributing](../architecture/contributing.md).
