"""Parsers provided by ``aiida_dftbplus``.

Registered with AiiDA through the ``aiida.parsers`` entry point in
``pyproject.toml``, under the name ``dftbplus``. It is the default parser of
:class:`~aiida_dftbplus.calculations.DftbPlusCalculation`, which sets
``metadata.options.parser_name = 'dftbplus'``.

:class:`DftbPlusParser` reads the files retrieved by the calculation, decides
whether the run succeeded, and attaches the scalars from ``detailed.out`` as
the ``output_parameters`` Dict. The complete set of retrieved files always
remains available on the ``retrieved`` FolderData, whatever the parser
concludes — a failed parse never loses data.

Unit conversions use CODATA 2018 values; energies are reported both in Hartree
and in eV, forces only in eV/Å.
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
    """Parse the output of a DFTB+ calculation.

    The parser has two jobs, in this order:

    1. **Classify the run.** Decide from ``dftb.out`` whether DFTB+ succeeded,
       failed fatally, or merely failed to converge, and return the matching
       exit code.
    2. **Extract the numbers.** On a clean run, pull the scalars out of
       ``detailed.out`` and attach them as ``output_parameters``.

    Both steps are implemented as pure static methods —
    :meth:`_detect_exit_code` and :meth:`_parse_detailed` — that take strings
    and return plain Python objects, so the parsing logic is testable without
    an AiiDA profile, a database, or a DFTB+ binary.

    Examples
    --------
    Read the parsed scalars from a finished calculation::

        from aiida import orm

        node = orm.load_node(1234)
        results = node.outputs.output_parameters.get_dict()
        print(results['total_energy_eV'], results['max_force_eV_Ang'])
    """

    def __init__(self, node):
        """Initialise the parser.

        Parameters
        ----------
        node : aiida.orm.nodes.process.process.ProcessNode
            The process node whose outputs are to be parsed.

        Raises
        ------
        aiida.common.exceptions.ParsingError
            If the node was not produced by a
            :class:`~aiida_dftbplus.calculations.DftbPlusCalculation`.
        """
        super().__init__(node)
        if not issubclass(node.process_class, DftbPlusCalculation):
            raise exceptions.ParsingError("Can only parse DftbPlusCalculation")

    def parse(self, **kwargs):
        """Parse the retrieved files and store the results in the database.

        ``dftb.out`` and ``detailed.out`` are the two files that must be there:
        without them nothing can be said about the run, which is exit code 300.
        Otherwise :meth:`_detect_exit_code` classifies the run, and a clean run
        gets its ``detailed.out`` scalars attached as ``output_parameters``.

        Parameters
        ----------
        **kwargs
            Passed by the engine; unused.

        Returns
        -------
        aiida.engine.ExitCode
            ``ExitCode(0)`` on success, otherwise one of the calculation's
            registered failure codes (300, 310, 320 or 330).
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
        """Translate a non-zero detection integer into the matching exit code.

        The diagnosis is logged at the severity it deserves: a convergence
        failure is a warning (the run produced usable intermediate output), a
        fatal DFTB+ error is an error.

        Parameters
        ----------
        code : int
            One of 310, 320 or 330, as returned by :meth:`_detect_exit_code`.

        Returns
        -------
        aiida.engine.ExitCode
            The registered exit code of the calculation class.

        Raises
        ------
        ValueError
            If ``code`` is not one of the three mapped values. This is a
            programming error, not a calculation failure, so it is raised
            rather than returned.
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
        """Classify a run from its output text.

        A pure function: it takes two strings and returns an integer, so it is
        directly testable without any AiiDA infrastructure.

        Parameters
        ----------
        stdout : str
            Content of ``dftb.out``.
        detailed : str
            Content of ``detailed.out``. Currently unused, and kept in the
            signature so callers need not know which file a given signature
            lives in.

        Returns
        -------
        int
            ``0`` for a clean run, otherwise ``310`` (fatal DFTB+ error),
            ``320`` (SCC not converged) or ``330`` (geometry not converged).

        Examples
        --------
        >>> DftbPlusParser._detect_exit_code('Geometry converged', '')
        0
        >>> DftbPlusParser._detect_exit_code('ERROR!\\n-> SCC is NOT converged', '')
        320

        Notes
        -----
        **The check order matters.** The specific convergence failures are
        detected before the generic ``ERROR!`` guard, because DFTB+ prints
        ``ERROR!`` on the line immediately before ``SCC is NOT converged`` when
        it exhausts ``MaxSCCIterations``. With the guard first, every
        recoverable SCC failure would be reported as a fatal 310 instead — the
        second example above is exactly that trap, and there is a regression
        test for it.

        Note that ``SCC is NOT converged`` appears in ``dftb.out`` (stdout),
        not in ``detailed.out``, so both checks read stdout.
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
        """Extract the scalars this plugin reports from ``detailed.out``.

        A geometry optimisation writes one result block per step, so wherever a
        quantity can repeat the **last** occurrence is taken — that is the
        converged value.

        Parameters
        ----------
        text : str
            Content of ``detailed.out``.

        Returns
        -------
        dict
            Whatever could be found, with these keys:

            ``total_energy_H``, ``total_energy_eV`` : float
                Total energy, in Hartree and eV. Absent if the file has none.
            ``fermi_energy_eV`` : float
                Fermi level in eV. Absent for a non-periodic system, or when
                DFTB+ did not print one.
            ``scc_converged`` : bool
                Always present.
            ``n_scc_iterations`` : int
                Number of SCC iterations of the last block.
            ``forces_eV_Ang`` : list of list of float
                One ``[Fx, Fy, Fz]`` per atom, converted from Ha/Bohr. Present
                only when forces were requested with ``CalculateForces``.
            ``max_force_eV_Ang`` : float
                Largest force magnitude — the number to watch when judging a
                relaxation.

        Examples
        --------
        >>> DftbPlusParser._parse_detailed('Total energy: -4.0733851869 H')['total_energy_H']
        -4.0733851869

        Notes
        -----
        This is a pure function over the file's text, so a new quantity can be
        added and tested without running DFTB+ at all. Nothing outside
        ``detailed.out`` is read here — ``band.out`` and the geometry files are
        retrieved but not parsed.
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
