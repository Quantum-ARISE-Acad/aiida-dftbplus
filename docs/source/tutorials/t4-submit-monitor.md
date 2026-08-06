# T4 — Submitting to the daemon and monitoring

**Goal.** Stop blocking your terminal. Submit calculations to the AiiDA daemon,
watch them, and diagnose one that fails.

**Prerequisites.** [T1](t1-single-point.md), and a profile **with a broker** —
`verdi status` must show a RabbitMQ line. Without one, `engine.submit` is
unavailable and you are limited to `engine.run`; see
[Prerequisites](../getting-started/prerequisites.md).

## run vs submit

| | `engine.run` / `run_get_node` | `engine.submit` |
| --- | --- | --- |
| Runs in | your Python process | a daemon worker |
| Your terminal | blocked until it finishes | free immediately |
| Returns | results **and** node | the node, straight away |
| Survives closing the terminal | no | yes |
| Needs a broker + running daemon | no | yes |
| Good for | one quick job, debugging | everything else |

## Step 1 — start the daemon

```shell
verdi daemon start 2        # two workers
verdi daemon status
```

```text
Profile: my_profile
Daemon is running as PID 31415 since 2026-08-06 09:12:03
## Active workers:
  PID    MEM %    CPU %  started
-----  -------  -------  -------------------
31416      1.2      0.0  2026-08-06 09:12:04
31417      1.2      0.0  2026-08-06 09:12:04
```

:::{tip}
If `verdi daemon status` reports a stale PID file, run `verdi daemon stop`
followed by `verdi daemon start`. If it *times out*, the workers are busy —
often copying files. That is a real failure mode of this plugin when a full SKF
set is shipped with every job; see
[Ship only what the run reads](../getting-started/skf-parameter-sets.md#ship-only-what-the-run-reads).
:::

## Step 2 — submit with a builder

The process builder is the discoverable way to fill inputs: it tab-completes,
it validates types as you assign, and `builder` printed in an interactive shell
shows everything you have set.

```python
from aiida import engine, orm
from aiida.plugins import CalculationFactory, DataFactory

builder = CalculationFactory("dftbplus").get_builder()
builder.code = orm.load_code("dftb+@localhost")
builder.parameters = DataFactory("dftbplus")(PARAMETERS)     # as in T1
builder.use_remote_skf_path = orm.Bool(True)
builder.structure = orm.Dict({"formula": "Si2"})
builder.metadata.label = "Si2 single point"
builder.metadata.description = "T4, submitted to the daemon"
builder.metadata.options.max_wallclock_seconds = 1800
builder.metadata.options.withmpi = False
builder.metadata.options.environment_variables = {"OMP_NUM_THREADS": "2"}

node = engine.submit(builder)
print(f"submitted <{node.pk}>")
```

`engine.submit` returns as soon as the process is stored. Everything after that
happens in a daemon worker.

## Step 3 — watch it

```shell
verdi process list                 # active processes only
verdi process list -a -p 1         # everything from the last day
verdi process show <PK>
verdi process report <PK>          # log messages, including parser warnings
verdi process watch <PK>           # follow until it finishes
```

A calculation moves through these states:

```text
Created -> Waiting (upload) -> Waiting (submit) -> Waiting (update)
        -> Waiting (retrieve) -> Waiting (parsing) -> Finished [0]
```

`verdi process list` shows the current one in the `State` column. `Finished [0]`
is success; `Finished [320]` is a calculation that ran and failed to converge;
`Excepted` means the *plugin or engine* raised an exception, which is a bug, not
a physics result.

## Step 4 — submit something that fails

Understanding failure is worth more than another successful run. Take the water
input from [T2](t2-relaxation.md) and starve the SCC cycle:

```python
parameters = PARAMETERS_WATER.copy()
parameters["Hamiltonian"]["DFTB"]["MaxSCCIterations"] = 2
parameters["Hamiltonian"]["DFTB"]["SCCTolerance"] = 1e-8
```

It finishes as:

```text
  PK  Created    Process label          Process State     Process status
----  ---------  ---------------------  ----------------  ----------------
1234  1m ago     DftbPlusCalculation    ⏹ Finished [320]
```

```shell
verdi process report 1234
```

```text
*** 1234: None
*** (empty scheduler output file)
*** (empty scheduler errors file)
*** 1 LOG MESSAGES:
+-> WARNING at 2026-08-06 09:20:41
 | SCC did not converge
```

Note the severity: a **warning**, not an error. Exit code 320 means DFTB+ ran
correctly and the physics did not converge — the outputs are still there and
still yours to inspect:

```shell
verdi calcjob outputcat 1234 dftb.out | tail -20
```

The stdout will contain `ERROR!` immediately followed by
`SCC is NOT converged`. The parser checks for the convergence message *before*
the generic `ERROR!`, which is why this comes back as a recoverable 320 rather
than a fatal 310. That ordering is deliberate and regression-tested — see
[Error handling](../explanation/error-handling.md).

Fixing it is [Control SCC convergence](../how-to/scc-convergence.md); automating
the fix is [T6](t6-custom-workchain.md).

## Step 5 — housekeeping

```shell
verdi process kill <PK>            # ask a running process to stop
verdi process pause <PK>           # freeze it
verdi process play <PK>            # resume
verdi node delete <PK> --dry-run   # see what would go with it
```

`verdi node delete` also deletes everything that descends from the node, which
is exactly what you want when clearing a failed batch and exactly what you do
not want by accident. Always look at `--dry-run` first.

## Step 6 — where the files actually are

While a calculation runs, its working directory lives on the computer:

```shell
verdi calcjob gotocomputer <PK>
```

That drops you into the remote working directory, where `dftb_in.hsd`, the SKF
files and the partial output can be inspected live. It is the fastest way to see
why a job that never finishes is stuck. After retrieval the same files (the
retrieved ones) are in the database and reachable with `verdi calcjob outputcat`
without touching the remote machine.

## What you learned

- `submit` needs a broker and a daemon; `run` needs neither but blocks.
- The builder is the discoverable way to assemble inputs, and carries `metadata`
  such as labels, walltime and environment variables.
- `Finished [320]` is a calculation that worked and did not converge;
  `Excepted` is a bug.
- `verdi process report`, `verdi calcjob outputcat` and
  `verdi calcjob gotocomputer` are the three tools for diagnosing a failure.

Next: [T5 — a high-throughput campaign](t5-high-throughput.md).
