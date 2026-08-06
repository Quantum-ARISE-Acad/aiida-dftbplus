"""A minimal WorkChain that retries a DFTB+ calculation which failed to converge."""

from aiida import orm
from aiida.engine import ToContext, WorkChain, calcfunction, while_
from aiida.plugins import CalculationFactory

DftbPlusCalculation = CalculationFactory("dftbplus")


@calcfunction
def loosen_scc(parameters, factor):
    """Return a copy of the parameters with more SCC iterations and gentler mixing."""
    updated = parameters.get_dict()
    dftb = updated["Hamiltonian"]["DFTB"]
    dftb["MaxSCCIterations"] = int(dftb.get("MaxSCCIterations", 100) * factor.value)
    dftb["_raw_mixer"] = "Mixer = Broyden {\n  MixingParameter = 0.05\n}"
    return orm.Dict(updated)


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

    def results(self):
        calculation = self.ctx.calculation
        if calculation.exit_status != 0:
            return self.exit_codes.ERROR_SCC_UNRECOVERABLE
        self.out_many(self.exposed_outputs(calculation, DftbPlusCalculation))
        return None
