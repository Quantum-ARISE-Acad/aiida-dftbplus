# Restart a failed or unconverged calculation

The plugin has **no restart machinery**. A `DftbPlusCalculation` runs once and
reports what happened. Restarting means launching a new calculation whose inputs
you derived from the old one — which is what this page shows, and what
[T6](../tutorials/t6-custom-workchain.md) automates.

## Restart the SCC cycle from converged charges

`charges.bin` is retrieved from every SCC run. Feeding it back skips the
expensive part of the cycle:

```python
import io

from aiida import orm

previous = orm.load_node(<PK>)

charges = orm.FolderData()
with previous.outputs.retrieved.open("charges.bin", "rb") as handle:
    charges.put_object_from_filelike(io.BytesIO(handle.read()), "charges.bin")
charges.store()

parameters = previous.inputs.parameters.get_dict()
parameters["Hamiltonian"]["DFTB"]["ReadInitialCharges"] = True

inputs = {
    "code": previous.inputs.code,
    "parameters": DataFactory("dftbplus")(parameters),
    "mat_files": charges,                      # lands next to dftb_in.hsd
    "use_remote_skf_path": previous.inputs.use_remote_skf_path,
    "metadata": {"options": dict(previous.get_options())},
}
```

Anything in `mat_files` is copied into the working directory, except a
`dftb_in.hsd`, which is skipped so the generated input always wins.

## Continue a geometry relaxation (exit code 330)

The relaxation ran out of `MaxSteps`. Start again from where it stopped, using
the geometry DFTB+ wrote:

```python
with previous.outputs.retrieved.open("geom.out.gen") as handle:
    last_geometry = handle.read().rstrip()

parameters = previous.inputs.parameters.get_dict()
parameters["Geometry"] = {"GenFormat": {"_raw": last_geometry}}
parameters["Driver"]["ConjugateGradient"]["MaxSteps"] = 500
```

Combine it with the charge restart above and the second run starts from both the
geometry and the charges of the first.

## Recover from a non-converged SCC cycle (exit code 320)

In rough order of what to try — details in
[Control SCC convergence](scc-convergence.md):

```python
dftb = parameters["Hamiltonian"]["DFTB"]
dftb["MaxSCCIterations"] = 500
dftb["_raw_mixer"] = "Mixer = Broyden {\n  MixingParameter = 0.05\n}"
dftb["_raw_filling"] = "Filling = Fermi {\n  Temperature [K] = 1000\n}"
```

## Do it properly, with provenance

The snippets above build a new `Dict` in plain Python, which leaves no record of
where it came from. Inside a `@calcfunction`, the link is recorded:

```python
from aiida.engine import calcfunction

@calcfunction
def restart_parameters(parameters, max_iterations):
    updated = parameters.get_dict()
    updated["Hamiltonian"]["DFTB"]["MaxSCCIterations"] = max_iterations.value
    updated["Hamiltonian"]["DFTB"]["ReadInitialCharges"] = True
    return orm.Dict(updated)

new_parameters = restart_parameters(previous.inputs.parameters, orm.Int(500))
```

Now `verdi node graph generate` on the second calculation shows the first one as
its ancestor, through the function that transformed the inputs.

## Do not use `RemoteData` to restart

`remote_folder` points at the working directory on the compute machine. It is
tempting to restart "in place" from it — but AiiDA cleans working directories
(`verdi calcjob cleanworkdir`), schedulers purge scratch, and nothing about that
folder is guaranteed to exist tomorrow. Restart from `retrieved`, which is in
the database and permanent.

## What cannot be restarted

Exit code 310 with a fatal DFTB+ error, and exit code 300 with no output at all,
are input or environment problems: a missing SKF pair, a typo inside a block, a
walltime kill, a full disk. Retrying them unchanged wastes queue time. Read
`dftb.out` and `_scheduler-stderr.txt` first — see
[Handle common errors](errors.md).
