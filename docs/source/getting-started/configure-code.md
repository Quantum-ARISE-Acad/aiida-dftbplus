# Registering the DFTB+ code

AiiDA needs a `Code` node describing *which executable on which computer* to
run. Registering it is a one-time step per machine.

## The command

```shell
verdi code create core.code.installed \
    --label dftb+ \
    --computer localhost \
    --default-calc-job-plugin dftbplus \
    --filepath-executable "$(which dftb+)" \
    --description "DFTB+ 24.1 from conda-forge" \
    --non-interactive
```

What each option does, and why it matters:

`--label dftb+`
: The name you will use later, as `dftb+@localhost`. Labels are unique per
  computer, so the same label can exist on several machines.

`--computer localhost`
: Which `Computer` the executable lives on. Must already be set up and
  configured — see [Prerequisites](prerequisites.md).

`--default-calc-job-plugin dftbplus`
: Ties the code to this plugin, so `verdi code test` and the process builder
  know what to do with it. Get this wrong and submission fails with a plugin
  mismatch.

`--filepath-executable`
: The **absolute path on the target computer**, not on your laptop.
  `$(which dftb+)` is correct only when the computer is localhost.

Verify it:

```shell
verdi code list
verdi code show dftb+@localhost
verdi code test dftb+@localhost
```

`verdi code test` checks that the file exists on the remote machine and is
executable. It does not run a calculation — that is
[your first calculation](first-calculation.md).

## Interactive setup

Leaving off `--non-interactive` walks you through the same fields with prompts,
which is easier the first time:

```shell
verdi code create core.code.installed
```

## From a configuration file

Reproducible and reviewable, which matters once several people share a cluster:

```yaml
# dftb-hpc.yml
label: 'dftb+'
description: 'DFTB+ 24.1, OpenMP build, on the cluster'
default_calc_job_plugin: 'dftbplus'
filepath_executable: '/apps/dftbplus/24.1/bin/dftb+'
computer: 'hpc-cluster'
prepend_text: |
    module load dftbplus/24.1
    export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
append_text: ''
```

```shell
verdi code create core.code.installed --config dftb-hpc.yml --non-interactive
```

`prepend_text` is the reliable place for `module load` lines and thread
settings: it is written into the submission script before the executable is
called, so every calculation using this code gets it without remembering.

## Several codes at once

Register one code per binary you care about — a serial and an MPI build, or two
versions you are comparing:

```shell
verdi code create core.code.installed --label dftb+-mpi --computer hpc-cluster \
    --default-calc-job-plugin dftbplus \
    --filepath-executable /apps/dftbplus/24.1-mpi/bin/dftb+ --non-interactive
```

Then pick per calculation with `orm.load_code('dftb+-mpi@hpc-cluster')`, and set
`metadata.options.withmpi = True` for the MPI one. The plugin defaults
`withmpi` to `False`, because a serial DFTB+ launched under `mpirun` will run
the same calculation N times rather than parallelise it.

## Quick setup for tests only

For throwaway work — the test suite and the bundled example — the plugin ships
helpers that create a localhost computer and find `dftb+` on `PATH`:

```python
from aiida_dftbplus import helpers

computer = helpers.get_computer()               # 'localhost-test', temp workdir
code = helpers.get_code("dftbplus", computer)   # finds dftb+ on PATH
```

These exist for convenience in tests and examples. For real work use
`verdi code create`, so the work directory and description are ones you chose.

Next: [Slater–Koster parameter sets](skf-parameter-sets.md) — the part that
decides whether your calculation is physically meaningful.
