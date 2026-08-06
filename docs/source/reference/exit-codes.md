# Exit codes

## The table

```{list-table}
:header-rows: 1
:widths: 8 30 12 50

* - Code
  - Name
  - Logged as
  - Condition
* - 0
  - —
  - —
  - Both essential files present and no failure signature in `dftb.out`
* - 300
  - `ERROR_MISSING_OUTPUT`
  - error
  - `dftb.out` or `detailed.out` absent from `retrieved`
* - 310
  - `ERROR_DFTB_FAILED`
  - error
  - `dftb.out` is empty, or contains `ERROR!` with no more specific signature
* - 320
  - `ERROR_SCC_NOT_CONVERGED`
  - warning
  - `dftb.out` contains `SCC is NOT converged` (case-insensitive)
* - 330
  - `ERROR_GEOMETRY_NOT_CONVERGED`
  - warning
  - `dftb.out` contains `Geometry did not converge` (case-insensitive)
```

Reference them by name in code:

```python
from aiida.plugins import CalculationFactory

DftbPlusCalculation = CalculationFactory("dftbplus")
DftbPlusCalculation.exit_codes.ERROR_SCC_NOT_CONVERGED.status      # 320
DftbPlusCalculation.exit_codes.ERROR_SCC_NOT_CONVERGED.message
```

## Detection order

```text
1. stdout is empty                 -> 310
2. "SCC IS NOT CONVERGED"          -> 320
3. "GEOMETRY DID NOT CONVERGE"     -> 330
4. "ERROR!"                        -> 310
5. otherwise                       -> 0
```

The generic guard is last on purpose: DFTB+ prints `ERROR!` on the line
immediately before the SCC verdict, so a guard-first order would report every
recoverable SCC failure as fatal. See
[Error handling](../explanation/error-handling.md).

All checks read `dftb.out`. `detailed.out` is passed to `_detect_exit_code` but
not currently examined — the signature is kept so callers need not know which
file a signature lives in.

## What each code implies for the outputs

| Code | `retrieved` | `output_parameters` | Recoverable |
| --- | --- | --- | --- |
| 0 | yes | yes | — |
| 300 | partial or empty | no | no — fix the environment |
| 310 | yes | no | no — fix the input |
| 320 | yes | no | yes — see [SCC convergence](../how-to/scc-convergence.md) |
| 330 | yes, including `geom.out.gen` | no | yes — see [Restart](../how-to/restart.md) |

`retrieved` is always attached when anything came back at all, whatever the exit
code. Nothing DFTB+ wrote is ever discarded.

(known-parsing-gaps)=

## Known parsing gaps

Honest limitations of the current parser, none of which lose data — everything
is still in `retrieved`.

**`n_scc_iterations` is often absent.** `_parse_detailed` looks for a
`N SCC iter` line in `detailed.out`. Recent DFTB+ versions (checked against a
2025 development build) do not print it; they print the per-iteration SCC table
in `dftb.out` instead. The key is simply missing from `output_parameters` — no
error, no warning. Count the rows of the SCC table in `dftb.out` if you need it.

**`scc_converged` is a string test, not a verdict.** It is
`"SCC is NOT converged" not in detailed.out`. For a non-SCC run — a band
structure with `MaxSCCIterations = 1`, for instance — it reports `True` while
nothing was converged at all. Interpret it only for genuine SCC runs.

**`band.out` is not parsed.** Retrieved, never read. No `BandsData`. See
[T3](../tutorials/t3-band-structure.md) for reading it yourself.

**Geometry files are not parsed.** `geom.out.gen` and `geom.out.xyz` are
retrieved as files; no `StructureData` is produced. See
[Export structures](../how-to/export-structures.md).

**Charges, dipole moments and orbital populations are not parsed.** All present
in `detailed.out`, none extracted. Adding one is a small change to
`_parse_detailed` plus a test — see
[Contributing](../architecture/contributing.md#adding-to-the-parser) — and old
calculations can be re-parsed afterwards without re-running DFTB+.

**Only `dftb.out` is inspected for failures.** A scheduler kill (walltime,
memory) leaves its trace in `_scheduler-stderr.txt`, which the parser does not
read; such a run usually surfaces as 300 or 310.
