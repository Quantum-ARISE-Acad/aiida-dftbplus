# Run on a remote machine or HPC scheduler

Nothing in the plugin changes when you move to a cluster: the transport and the
scheduler are AiiDA's, and the calculation is the same. What changes is the
computer setup and the resource options.

## Set up the computer

```shell
verdi computer setup \
    --label hpc-cluster \
    --hostname login.cluster.example \
    --transport core.ssh \
    --scheduler core.slurm \
    --work-dir /scratch/{username}/aiida \
    --mpiprocs-per-machine 32 \
    --shebang '#!/bin/bash' \
    --non-interactive

verdi computer configure core.ssh hpc-cluster \
    --username myaccount \
    --key-filename ~/.ssh/id_ed25519 \
    --safe-interval 60 \
    --non-interactive

verdi computer test hpc-cluster
```

`{username}` in the work directory is expanded by AiiDA to the remote user name.
`--safe-interval 60` is the minimum seconds between SSH connections — keep it
generous on a shared login node.

Available schedulers: `core.slurm`, `core.pbspro`, `core.torque`, `core.lsf`,
`core.sge`, and `core.direct` for no queue at all.

## Register the code there

```shell
verdi code create core.code.installed \
    --label dftb+ --computer hpc-cluster \
    --default-calc-job-plugin dftbplus \
    --filepath-executable /apps/dftbplus/24.1/bin/dftb+ \
    --prepend-text 'module load dftbplus/24.1' \
    --non-interactive
```

`prepend_text` lands in the submission script before the executable runs. It is
the right place for `module load`, `source activate`, and thread settings.

## Ask for resources

```python
builder.metadata.options.resources = {
    "num_machines": 1,
    "num_mpiprocs_per_machine": 1,
    "num_cores_per_mpiproc": 8,
}
builder.metadata.options.max_wallclock_seconds = 3600
builder.metadata.options.queue_name = "compute"
builder.metadata.options.account = "project-1234"
builder.metadata.options.withmpi = False
builder.metadata.options.environment_variables = {"OMP_NUM_THREADS": "8"}
```

The plugin's defaults are one machine, one MPI process, `withmpi=False`, and a
two-hour walltime.

:::{important}
**DFTB+ parallelism is usually OpenMP, not MPI.** The standard conda build is
threaded, not MPI-enabled. Running it under `mpirun` gives you N identical
copies of the same calculation, each writing over the others' output.

Set `withmpi=True` only for a genuinely MPI-enabled build, and then request
`num_mpiprocs_per_machine` accordingly. For the usual threaded build, keep
`withmpi=False` and control `OMP_NUM_THREADS` — and always set it explicitly,
because DFTB+ will otherwise use every core on the node while the scheduler
thinks it gave you one.
:::

## Where the SKF files should live

On a cluster, put the parameter set on the shared filesystem once and use
`use_remote_skf_path=True`. Transferring a 1.5 GB set over SSH for every job is
the worst thing you can do to a login node — and to your batch throughput.

```python
builder.use_remote_skf_path = orm.Bool(True)
# the Prefix in the input must be the path on the *cluster*
```

Ship `skf_files` only when the folder is small (a few element pairs) and
reproducibility outweighs the transfer.

## Keep the daemon healthy

```shell
verdi daemon start 4                      # one worker per few hundred jobs
verdi config set daemon.timeout 60        # be patient with a slow login node
verdi config list | grep -i interval
```

If `verdi daemon status` starts timing out during a batch, the workers are
almost certainly blocked on file transfer, not on physics. Check what you are
uploading before adding workers.

## Debugging a remote job

```shell
verdi calcjob gotocomputer <PK>     # ssh straight into the working directory
verdi calcjob outputcat <PK> _scheduler-stderr.txt
verdi calcjob outputcat <PK> _scheduler-stdout.txt
verdi process report <PK>
```

`_scheduler-stderr.txt` is where a walltime kill, an out-of-memory kill, or a
missing module shows up — none of which DFTB+ ever sees, and none of which the
parser can classify beyond exit code 300.
