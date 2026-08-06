# T6 — Writing a WorkChain on top of the CalcJob

**Goal.** Turn "the SCC did not converge, try again with gentler settings" from
something you do by hand into something the engine does for you.

**Prerequisites.** [T4](t4-submit-monitor.md).

:::{important}
**This plugin ships no workflows.** There is no `aiida.workflows` entry point,
no `BaseRestartWorkChain`, no relax-then-static chain. Everything in this
tutorial is code *you* write on top of `DftbPlusCalculation`. That is a real
limitation, and it is the reason this tutorial exists.
:::

Download the finished file: {download}`dftb_scc_workchain.py <../_static/dftb_scc_workchain.py>`

## Why a WorkChain rather than a script

A Python script that loops and resubmits works — until your terminal closes.
A `WorkChain` is a *process*: the daemon runs it, its state is checkpointed in
the database, it survives a restart, and — the part that matters for science —
**every attempt it makes is recorded in the provenance graph**, linked to the
inputs that produced it. A script leaves no such record.

## Step 1 — the skeleton

```python
from aiida import orm
from aiida.engine import ToContext, WorkChain, calcfunction, while_
from aiida.plugins import CalculationFactory

DftbPlusCalculation = CalculationFactory("dftbplus")


class DftbSccWorkChain(WorkChain):
    """Run a DFTB+ calculation; on exit code 320, retry with a gentler SCC cycle."""

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.expose_inputs(DftbPlusCalculation, namespace="dftb")
        spec.input("max_attempts", valid_type=orm.Int, default=lambda: orm.Int(2))
        spec.outline(
            cls.setup,
            while_(cls.should_run)(
                cls.run_calculation,
                cls.inspect_calculation,
            ),
            cls.results,
        )
        spec.expose_outputs(DftbPlusCalculation)
        spec.exit_code(400, "ERROR_SCC_UNRECOVERABLE", message="SCC still not converged after retrying.")
        spec.exit_code(401, "ERROR_CALCULATION_FAILED", message="The calculation failed in a way we do not handle.")
```

`expose_inputs(..., namespace="dftb")` is the detail worth copying. Exposing the
calculation's inputs at the top level clashes with the workchain's own
`metadata` port and fails at run time with `unsupported metadata key: options`.
Under a namespace, the calculation's inputs are passed as `dftb={...}` and stay
separate.

## Step 2 — the steps

```python
    def setup(self):
        self.ctx.parameters = self.inputs.dftb.parameters
        self.ctx.attempt = 0
        self.ctx.is_finished = False

    def should_run(self):
        return not self.ctx.is_finished and self.ctx.attempt < self.inputs.max_attempts.value

    def run_calculation(self):
        self.ctx.attempt += 1
        inputs = self.exposed_inputs(DftbPlusCalculation, namespace="dftb")
        inputs["parameters"] = self.ctx.parameters
        node = self.submit(DftbPlusCalculation, **inputs)
        self.report(f"attempt {self.ctx.attempt}: launched <{node.pk}>")
        return ToContext(calculation=node)
```

`return ToContext(calculation=node)` is how a workchain waits: the step returns
immediately, the engine parks the workchain until that calculation finishes, and
the finished node reappears as `self.ctx.calculation`. The daemon is free the
whole time.

## Step 3 — decide what to do about the result

```python
    def inspect_calculation(self):
        calculation = self.ctx.calculation
        status = calculation.exit_status

        if status == 0:
            self.ctx.is_finished = True
            self.report(f"<{calculation.pk}> finished cleanly")
            return None

        if status != DftbPlusCalculation.exit_codes.ERROR_SCC_NOT_CONVERGED.status:
            self.ctx.is_finished = True
            self.report(f"<{calculation.pk}> failed with {status}; not handled here")
            return self.exit_codes.ERROR_CALCULATION_FAILED

        self.report(f"<{calculation.pk}> did not converge; loosening the SCC cycle")
        self.ctx.parameters = loosen_scc(self.ctx.parameters, orm.Float(5))
        return None
```

Compare against `DftbPlusCalculation.exit_codes.ERROR_SCC_NOT_CONVERGED.status`
rather than the literal `320`. The name is the contract; the number is an
implementation detail that this workchain should not have to know.

Everything else is handled by *not* handling it: an unrecognised failure returns
401 and stops, which is the right default. A workchain that silently retries
every failure will happily burn a queue allocation on a typo in your input.

## Step 4 — modify inputs with a calcfunction, never in place

```python
@calcfunction
def loosen_scc(parameters, factor):
    """Return a copy of the parameters with more SCC iterations and gentler mixing."""
    updated = parameters.get_dict()
    dftb = updated["Hamiltonian"]["DFTB"]
    dftb["MaxSCCIterations"] = int(dftb.get("MaxSCCIterations", 100) * factor.value)
    dftb["_raw_mixer"] = "Mixer = Broyden {\n  MixingParameter = 0.05\n}"
    return orm.Dict(updated)
```

This is the rule that makes the difference between a workflow and a script.
A `@calcfunction` takes stored nodes, returns new stored nodes, and the engine
records the link between them. Six months later the provenance graph shows that
the second attempt's parameters were *derived from* the first attempt's by this
function — with the factor that was used. Mutating a stored node instead is
impossible anyway (AiiDA nodes are immutable once stored), and building the new
`Dict` outside a calcfunction loses the link.

Note `_raw_mixer`: any key starting with `_raw` is written to the HSD file
verbatim, which is how a block the dictionary form does not model gets in.

## Step 5 — collect the outputs

```python
    def results(self):
        calculation = self.ctx.calculation
        if calculation.exit_status != 0:
            return self.exit_codes.ERROR_SCC_UNRECOVERABLE
        self.out_many(self.exposed_outputs(calculation, DftbPlusCalculation))
        return None
```

`expose_outputs` + `out_many` attach the last calculation's outputs to the
workchain, so a caller sees `workchain.outputs.output_parameters` and never has
to know how many attempts it took.

## Step 6 — run it

```python
from aiida import engine, orm
from aiida.plugins import DataFactory
from dftb_scc_workchain import DftbSccWorkChain

parameters = PARAMETERS_WATER.copy()
parameters["Hamiltonian"]["DFTB"]["MaxSCCIterations"] = 2      # deliberately too few
parameters["Hamiltonian"]["DFTB"]["SCCTolerance"] = 1e-8       # deliberately too tight

results, node = engine.run_get_node(
    DftbSccWorkChain,
    dftb={
        "code": orm.load_code("dftb+@localhost"),
        "parameters": DataFactory("dftbplus")(parameters),
        "use_remote_skf_path": orm.Bool(True),
        "metadata": {"options": {"max_wallclock_seconds": 600, "withmpi": False}},
    },
)
```

Real output from that run:

```text
[REPORT] [6|DftbSccWorkChain|run_calculation]: attempt 1: launched <7>
[REPORT] [6|DftbSccWorkChain|inspect_calculation]: <7> did not converge; loosening the SCC cycle
[REPORT] [6|DftbSccWorkChain|run_calculation]: attempt 2: launched <13>
[REPORT] [6|DftbSccWorkChain|inspect_calculation]: <13> finished cleanly
workchain exit: 0
outputs: ['output_parameters', 'remote_folder', 'retrieved']
 child DftbPlusCalculation 320
 child loosen_scc 0
 child DftbPlusCalculation 0
{'total_energy_H': -4.0049258602, 'total_energy_eV': -108.97958446845,
 'fermi_energy_eV': -1.5951502185484, 'scc_converged': True}
```

The three children tell the whole story: a failed calculation, the calcfunction
that repaired the inputs, and the successful retry. That is the provenance a
script cannot give you.

For production, submit it to the daemon instead:

```python
node = engine.submit(DftbSccWorkChain, dftb={...})
```

## Step 7 — make it importable by the daemon

`engine.run` works with the class imported from a local file. `engine.submit`
does not: the daemon worker is a different process and must be able to import
your workchain. Two options:

1. **Put it on the `PYTHONPATH`** the daemon sees, then restart the daemon:

   ```shell
   verdi config set daemon.worker_process_slots 4
   export PYTHONPATH=$HOME/my_workflows:$PYTHONPATH
   verdi daemon restart --reset
   ```

2. **Package it** with an `aiida.workflows` entry point, which is what a plugin
   would do:

   ```toml
   [project.entry-points."aiida.workflows"]
   "dftbplus.scc" = "my_package.workchains:DftbSccWorkChain"
   ```

   Then `WorkflowFactory("dftbplus.scc")` works everywhere, including
   `verdi process show`.

## Where to take it next

Obvious extensions, in rough order of usefulness:

- **Relax then static.** Run a `Driver` calculation, read `geom.out.gen` out of
  `retrieved`, feed it into a static calculation as the new `Geometry`.
- **Handle 330** (geometry not converged) by restarting from the last geometry
  with a larger `MaxSteps`.
- **Restart from `charges.bin`** instead of starting the SCC cycle from scratch —
  see [T3](t3-band-structure.md) for the mechanics and
  [Restart a calculation](../how-to/restart.md).
- **Use `BaseRestartWorkChain`** from `aiida-core`, which implements the
  attempt/inspect/handle loop with a `@process_handler` decorator and is what a
  mature plugin would build on.

## What you learned

- Expose a calculation's inputs under a **namespace**, or its `metadata` collides
  with the workchain's.
- `ToContext` is how a workchain waits without occupying a worker.
- Compare against named exit codes, not numbers, and refuse to handle failures
  you did not anticipate.
- Modify inputs inside a `@calcfunction` so the provenance graph records why the
  second attempt differed from the first.
- `submit` needs the class to be importable by the daemon; `run` does not.
