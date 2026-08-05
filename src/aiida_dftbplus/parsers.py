"""
Parsers provided by aiida_dftbplus.

Register parsers via the "aiida.parsers" entry point in pyproject.toml.

:class:`DftbPlusParser` reads the files retrieved by
:class:`~aiida_dftbplus.calculations.DftbPlusCalculation`, decides whether the
run succeeded, and attaches the scalars from ``detailed.out`` as the
``output_parameters`` Dict. The complete set of retrieved files always remains
available on the ``retrieved`` FolderData, whatever the parser concludes.
"""

from __future__ import annotations

import re

from aiida.common import exceptions
from aiida.engine import ExitCode
from aiida.orm import Dict
from aiida.parsers.parser import Parser
from aiida.plugins import CalculationFactory

DftbPlusCalculation = CalculationFactory("dftbplus")

# Unit conversions (CODATA 2018)
HARTREE_TO_EV = 27.211386245988
BOHR_TO_ANG = 0.529177210903
HA_BOHR_TO_EV_ANG = 51.4220674763259

# Numeric token: plain or E-notation
_NUM = r"-?[\d.]+(?:[eE][+-]?\d+)?"


class DftbPlusParser(Parser):
    """
    Parser class for parsing output of a DFTB+ calculation.
    """

    def __init__(self, node):
        """
        Initialize Parser instance

        Checks that the ProcessNode being passed was produced by a DftbPlusCalculation.

        :param node: ProcessNode of calculation
        :param type node: :class:`aiida.orm.nodes.process.process.ProcessNode`
        """
        super().__init__(node)
        if not issubclass(node.process_class, DftbPlusCalculation):
            raise exceptions.ParsingError("Can only parse DftbPlusCalculation")

    def parse(self, **kwargs):
        """
        Parse outputs, store results in database.

        ``dftb.out`` and ``detailed.out`` are the two files that must be there:
        without them nothing can be said about the run, which is exit code 300.
        Otherwise :meth:`_detect_exit_code` classifies the run, and a clean run
        gets its ``detailed.out`` scalars attached as ``output_parameters``.

        :returns: an exit code, if parsing fails (or nothing if parsing succeeds)
        """
        files_retrieved = self.retrieved.list_object_names()

        # --- 300: the two files that must always be present ---
        for expected in ("dftb.out", "detailed.out"):
            if expected not in files_retrieved:
                self.logger.error(f"Found files '{files_retrieved}', expected to find '{expected}'")
                return self.exit_codes.ERROR_MISSING_OUTPUT

        with self.retrieved.open("dftb.out", "r") as handle:
            stdout = handle.read()
        with self.retrieved.open("detailed.out", "r") as handle:
            detailed = handle.read()

        code = self._detect_exit_code(stdout, detailed)
        if code != 0:
            return self._map_failure(code)

        # --- Success ---
        self.logger.info("Parsing 'detailed.out'")
        self.out("output_parameters", Dict(self._parse_detailed(detailed)))

        return ExitCode(0)

    def _map_failure(self, code: int):
        """Translate a non-zero detection integer into the matching ExitCode.

        The diagnosis is logged at the severity it deserves: a convergence
        failure is a warning (the run produced usable intermediate output), a
        fatal DFTB+ error is an error.
        """
        if code == 310:
            self.logger.error("DFTB+ reported a fatal error")
            return self.exit_codes.ERROR_DFTB_FAILED
        if code == 320:
            self.logger.warning("SCC did not converge")
            return self.exit_codes.ERROR_SCC_NOT_CONVERGED
        if code == 330:
            self.logger.warning("Geometry relaxation did not converge within MaxSteps")
            return self.exit_codes.ERROR_GEOMETRY_NOT_CONVERGED
        raise ValueError(f"_map_failure called with unmapped detection code {code!r}")

    @staticmethod
    def _detect_exit_code(stdout: str, detailed: str) -> int:  # pylint: disable=unused-argument
        """
        Pure-function exit-code detection: takes two strings, returns an integer.

        Called by :meth:`parse` and directly testable without any AiiDA
        infrastructure. Returns 0 on success, or the matching exit code.

        **The check order matters.** The specific convergence failures are
        detected before the generic ``ERROR!`` guard, because DFTB+ prints
        ``ERROR!`` on the line immediately before ``SCC is NOT converged`` when
        it exhausts MaxSCCIterations. With the guard first, every recoverable
        SCC failure would be reported as a fatal 310 instead.

        Note that ``SCC is NOT converged`` appears in ``dftb.out`` (stdout),
        not in ``detailed.out`` — so both checks read stdout.

        :param stdout: content of dftb.out
        :param detailed: content of detailed.out (currently unused; kept so
            callers need not care which file a signature lives in)
        :returns: 0, 310, 320 or 330
        """
        # 310 — an empty stdout means the process died before producing output
        if not stdout.strip():
            return 310

        stdout_upper = stdout.upper()

        # 320 — SCC not converged (before the generic ERROR! guard)
        if "SCC IS NOT CONVERGED" in stdout_upper:
            return 320

        # 330 — geometry not converged (before the generic ERROR! guard)
        if "GEOMETRY DID NOT CONVERGE" in stdout_upper:
            return 330

        # 310 — generic fatal error; the fallback, so it is checked last
        if "ERROR!" in stdout_upper:
            return 310

        return 0

    @staticmethod
    def _parse_detailed(text: str) -> dict:
        """Extract the relevant scalars from ``detailed.out``.

        A geometry optimisation writes one result block per step, so wherever a
        quantity can repeat the **last** occurrence is taken — that is the
        converged value.

        Pure function — directly testable without AiiDA infrastructure.
        """
        result = {}

        # Total energy (Hartree → eV). Case-insensitive: DFTB+ prints "Total energy:".
        matches = re.findall(r"Total energy:\s+([-\d.]+)\s+H", text, re.IGNORECASE)
        if matches:
            result["total_energy_H"] = float(matches[-1])
            result["total_energy_eV"] = float(matches[-1]) * HARTREE_TO_EV

        # Fermi energy — the label varies by DFTB+ version: "Fermi level:" or "Fermi energy:"
        matches = re.findall(r"Fermi (?:level|energy):\s+([-\d.]+)\s+H", text, re.IGNORECASE)
        if matches:
            result["fermi_energy_eV"] = float(matches[-1]) * HARTREE_TO_EV

        # SCC convergence flag — note the inversion: the file states the negative case
        result["scc_converged"] = "SCC is NOT converged" not in text

        # Number of SCC iterations
        match = re.search(r"(\d+)\s+SCC iter", text)
        if match:
            result["n_scc_iterations"] = int(match.group(1))

        # Forces (Ha/Bohr → eV/Å) — the block starts with "Total Forces"
        forces = []
        in_forces = False
        for line in text.splitlines():
            if "Total Forces" in line:
                in_forces = True
                forces = []
                continue
            if in_forces:
                nums = re.findall(_NUM, line)
                if len(nums) >= 4:
                    # Column 0 is the atom index; Fx Fy Fz are columns 1-3
                    forces.append([float(x) * HA_BOHR_TO_EV_ANG for x in nums[1:4]])
                else:
                    in_forces = False
        if forces:
            result["forces_eV_Ang"] = forces
            result["max_force_eV_Ang"] = max(sum(f**2 for f in row) ** 0.5 for row in forces)

        return result
