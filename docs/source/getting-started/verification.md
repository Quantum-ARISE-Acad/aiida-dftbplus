# Verification checklist

Run these before you trust anything. Each command proves one link in the chain,
in the order the chain is used. If one fails, fix it before moving on — the
later checks will not be meaningful.

## 1. AiiDA itself

```shell
verdi status
```

```text
 ✔ version:     AiiDA v2.8.0
 ✔ config:      /home/you/.aiida
 ✔ profile:     my_profile
 ✔ storage:     Storage for 'my_profile' [open] ...
 ✔ broker:      RabbitMQ v3.12.1 @ amqp://guest:guest@127.0.0.1:5672
 ✔ daemon:      Daemon is running with PID 12345
```

A missing broker line is not fatal — it means `engine.submit()` is unavailable
and you must use `engine.run()`. A stale-PID daemon message is fixed with
`verdi daemon stop && verdi daemon start`.

## 2. The plugin is registered

```shell
verdi plugin list aiida.calculations | grep dftbplus
verdi plugin list aiida.parsers      | grep dftbplus
verdi plugin list aiida.data         | grep dftbplus
verdi data dftbplus --help
```

All four must respond. The last one proves the CLI entry point loaded too.

## 3. The full input specification loads

```shell
verdi plugin list aiida.calculations dftbplus
```

This instantiates the process spec. It prints every input port with its type
and whether it is required — the same information as
[the I/O contract](../architecture/io-contract.md), straight from the code.

## 4. The computer answers

```shell
verdi computer test localhost
```

```text
Report: Testing computer<localhost> for user<you@example.com>...
 * Opening connection... [OK]
 * Checking for spurious output... [OK]
 * Getting number of jobs from scheduler... [OK]
 * Determining remote user name... [OK]
 * Creating and deleting temporary file... [OK]
Success: all 5 tests succeeded
```

## 5. The code exists on that computer

```shell
verdi code test dftb+@localhost
```

## 6. DFTB+ actually runs

Not through AiiDA — directly, so a failure here is unambiguously DFTB+'s:

```shell
dftb+ --version
```

## 7. The SKF files are readable and complete

```shell
ls "$SKF_DIR" | wc -l                    # n^2 for n elements
ls "$SKF_DIR"/H-H.skf                    # the pair you are about to use
sed -n '2p' "$SKF_DIR"/H-H.skf           # Ed Ep Es SPE Ud Up Us fd fp fs
```

For `H-H.skf` the second line looks like

```text
0 0 -0.238547 0.000000 0 0 0.391066 0 0 1
```

— `Ed` and `Ep` are zero and `fs` is 1, i.e. an s-only element with one
electron. That is the cross-check that `MaxAngularMomentum { H = "s" }` is
right. Details on the [SKF page](skf-parameter-sets.md).

## 8. End to end

Run [your first calculation](first-calculation.md) and confirm:

```{list-table}
:header-rows: 1
:widths: 50 50

* - Check
  - Expected
* - `node.exit_status`
  - `0`
* - `node.is_finished_ok`
  - `True`
* - `'output_parameters' in node.outputs`
  - `True`
* - `node.outputs.output_parameters['scc_converged']`
  - `True`
* - `'dftb.out' in node.outputs.retrieved.list_object_names()`
  - `True`
```

## 9. The test suite, if you installed from source

```shell
pytest -v
```

Expect **39 passed**. Without a `dftb+` binary on `PATH` the end-to-end test
skips itself: 38 passed, 1 skipped. Any other result is a real failure — see
[Contributing](../architecture/contributing.md).

## If something fails

| Symptom | Most likely cause |
| --- | --- |
| `verdi` works but no `dftbplus` entry points | The plugin is installed in a different environment from `verdi` |
| `verdi computer test` fails on connection | SSH configuration, or the work directory does not exist / is not writable |
| Calculation ends `[300]` | DFTB+ never produced output — read `_scheduler-stderr.txt` in `retrieved` |
| Calculation ends `[310]` immediately | Almost always the SKF path or a typo inside a block; `verdi calcjob outputcat <PK> dftb.out` names it |
| Calculation hangs in `Waiting` | The daemon is not running, or the scheduler queue is full |

More in [Handle common errors](../how-to/errors.md).
