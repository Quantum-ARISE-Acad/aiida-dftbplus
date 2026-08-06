# Error handling and the recovery philosophy

## The position, stated plainly

**This plugin classifies failures. It does not recover from them.**

There is no restart logic, no retry, no error handler, no `WorkChain`. A
calculation runs once, and the plugin's job is to say precisely what happened so
that *you* — or a workflow you write — can decide what to do.

That is a deliberate scope decision, not an omission waiting to be fixed at the
`CalcJob` level. A `CalcJob` that retried itself would hide the failure from the
provenance graph: you would see one node that "worked", with no record of the
three attempts behind it. AiiDA's design puts recovery in a `WorkChain`, where
each attempt is its own node and the graph shows the whole story. See
[T6](../tutorials/t6-custom-workchain.md).

## The four exit codes

```{list-table}
:header-rows: 1
:widths: 8 30 20 42

* - Code
  - Name
  - Severity logged
  - Meaning
* - 300
  - `ERROR_MISSING_OUTPUT`
  - error
  - `dftb.out` or `detailed.out` never came back. Nothing can be said.
* - 310
  - `ERROR_DFTB_FAILED`
  - error
  - DFTB+ stopped deliberately, or produced no output at all.
* - 320
  - `ERROR_SCC_NOT_CONVERGED`
  - warning
  - Ran fine; the charges did not converge. Recoverable.
* - 330
  - `ERROR_GEOMETRY_NOT_CONVERGED`
  - warning
  - Ran fine; the relaxation ran out of steps. Recoverable.
```

The severities are part of the message. An error means "something is wrong with
your setup"; a warning means "the physics did not converge, and the run is still
useful".

## The check order, and why it is load-bearing

`_detect_exit_code` tests in this order:

1. empty stdout → 310
2. `SCC IS NOT CONVERGED` → 320
3. `GEOMETRY DID NOT CONVERGE` → 330
4. `ERROR!` → 310
5. otherwise → 0

The generic `ERROR!` guard is **last**, and that is the single most important
line of the parser. When DFTB+ exhausts `MaxSCCIterations` it prints:

```text
ERROR!
-> SCC is NOT converged, maximal SCC iterations exceeded
```

With the guard first, every recoverable SCC failure would be reported as a fatal
310, and any workflow keyed on 320 would never fire. This was found on a real
batch — one material out of six — and there is a regression test named for it,
`test_detect_scc_failure_wins_over_generic_error`.

The general rule for anyone adding a signature: **specific before generic**.

## Why unconverged results are not attached

On any non-zero exit code the parser attaches no `output_parameters`. The energy
of a non-converged SCC cycle is a number, and numbers that exist get plotted.
Withholding it makes "give me all results" return only results.

Nothing is discarded. `retrieved` holds every file, and you can read the
unconverged energy yourself in one line if you want it:

```python
with node.outputs.retrieved.open("detailed.out") as handle:
    print(handle.read())
```

## What "exit status 0" does and does not mean

It means: the two essential files came back, and `dftb.out` contains none of the
known failure signatures.

It does **not** mean the numbers are right. A wrong parameter set, a wrong
`MaxAngularMomentum`, a DFTB3 set used without its third-order terms — all
produce a clean run and wrong physics. No parser can catch that.

## Where recovery belongs

| Failure | Who should fix it |
| --- | --- |
| 320 SCC not converged | A `WorkChain`: more iterations, gentler mixing, restart from charges |
| 330 geometry not converged | A `WorkChain`: continue from `geom.out.gen` with more steps |
| 310 fatal DFTB+ error | You: the input or the parameter set is wrong |
| 300 no output | You: walltime, memory, modules, disk — read the scheduler files |

A workflow that retries everything indiscriminately will spend a queue
allocation on a typo. The one in [T6](../tutorials/t6-custom-workchain.md)
handles 320 and refuses everything else on purpose.

## Exceptions are a different thing

`Excepted` in `verdi process list` means the plugin or the engine raised, not
that DFTB+ failed. That is a bug. The traceback is in `verdi process report`.

One historical example worth knowing: passing `None` paths in
`local_copy_list` passed the unit tests and then raised
`PluginInternalError: local_copy_list format problem` at upload time, because
`presubmit` validates the entries with `validate_list_of_string_tuples` even
though the copy itself tolerates `None`. Twenty-six calculations died that way.
The test now runs the same validator, so the format cannot regress silently.
