# Calculation lifecycle

The sequence, with the code that runs at each step and the state you can observe
from `verdi`.

```{graphviz} ../_static/diagrams/lifecycle.dot
:caption: Builder to output nodes. Blue is plugin code; everything else is AiiDA or DFTB+.
:align: center
```

## The steps

```{list-table}
:header-rows: 1
:widths: 5 22 33 40

* - #
  - Stage
  - Who runs it
  - What happens
* - 1
  - Builder / inputs
  - you
  - Nodes are assembled. Nothing is stored yet.
* - 2
  - `submit` / `run`
  - engine
  - Input nodes are stored, a `CalcJobNode` is created and linked. Inputs become immutable.
* - 3
  - Input validation
  - `validate_inputs`
  - Exactly one of `parameters` / `dftb_input`. Raises `ValueError` here, before anything is uploaded.
* - 4
  - `prepare_for_submission`
  - **plugin**
  - HSD generated and patched, `dftb_in.hsd` written to the sandbox, `mat_files` copied, `CalcInfo` returned.
* - 5
  - `presubmit`
  - engine
  - Validates `local_copy_list` entries, writes the submission script from the code's `prepend_text` and the resource options.
* - 6
  - Upload
  - engine + transport
  - Sandbox contents and `local_copy_list` nodes are copied to the working directory. State: `Waiting (upload)`.
* - 7
  - Submit
  - engine + scheduler
  - The job enters the queue. State: `Waiting (submit)`, then `Waiting (update)` while it polls.
* - 8
  - Execution
  - DFTB+
  - `dftb+ > dftb.out 2> dftb.err`, reading `dftb_in.hsd` from the working directory.
* - 9
  - Retrieve
  - engine + transport
  - The eight names in `retrieve_list` are copied back, plus the two scheduler files. State: `Waiting (retrieve)`.
* - 10
  - `parse`
  - **plugin**
  - Files classified, exit code returned, `output_parameters` attached on success. State: `Waiting (parsing)`.
* - 11
  - Terminal
  - engine
  - `Finished [exit_status]`. Outputs sealed; the node is immutable.
```

The plugin runs in exactly two of those eleven rows.

## Observing it

```shell
verdi process list                # active, with the current state
verdi process show <PK>           # inputs, outputs, links
verdi process report <PK>         # log messages, including parser warnings
verdi calcjob gotocomputer <PK>   # step 8, live, in the working directory
```

## The working directory at step 8

```text
_aiidasubmit.sh      # written by the engine from CodeInfo + options
dftb_in.hsd          # written by the plugin (step 4)
H-H.skf, ...         # from local_copy_list, if skf_files was given
geometry.gen, ...    # from mat_files, via the sandbox
dftb.out             # stdout, created at step 8
dftb.err             # stderr
detailed.out         # DFTB+'s main output
dftb_pin.hsd         # DFTB+'s processed input
charges.bin
band.out
geom.out.gen         # only if a Driver relaxed something
geom.out.xyz
```

## Where each failure appears

```{list-table}
:header-rows: 1
:widths: 20 30 50

* - Stage
  - Failure looks like
  - Typical cause
* - 3
  - `ValueError` at submission
  - Neither or both of `parameters` / `dftb_input`
* - 4
  - `Excepted`, traceback in the report
  - A bug in the plugin
* - 5
  - `PluginInternalError: local_copy_list format problem`
  - `None` paths in the copy list — regression-tested
* - 6–7
  - Stuck in `Waiting`
  - Daemon down, transport failing, or workers blocked copying files
* - 8
  - Exit code 310 or 320/330
  - DFTB+ stopped, or did not converge
* - 9
  - Exit code 300
  - The job died before writing output — read `_scheduler-stderr.txt`
* - 10
  - `Excepted` in the parser
  - A bug in the parser
```

## Timing, from a real run

A two-atom silicon calculation on localhost: DFTB+ takes under a second, the
engine's polling makes the whole process take a few seconds, and the daemon
polls the scheduler on an interval you can tune
(`verdi computer configure ... --safe-interval`).

That ratio is the reason for the plugin's central design decision: when the
science takes 0.79 s, anything the engine copies twice dominates the run
completely. See
[Design decisions](design-decisions.md#skf-files-bypass-the-sandbox).
