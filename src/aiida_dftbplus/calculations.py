"""
Calculations provided by aiida_dftbplus.

Register calculations via the "aiida.calculations" entry point in pyproject.toml.

This module provides a single CalcJob, :class:`DftbPlusCalculation`, that wraps
one DFTB+ execution: it assembles ``dftb_in.hsd`` (plus the Slater-Koster and
material files the run needs), launches the executable, and retrieves every
output file DFTB+ produces.

**Inputs**

- ``code`` — the registered DFTB+ executable (Code node).
- ``parameters`` — Dict (optional): structured DFTB+ input as a nested Python
  dict mirroring the HSD block structure. When present, ``dftb_in.hsd`` is
  generated via :meth:`DftbPlusCalculation._dict_to_hsd`, which makes every
  DFTB+ setting queryable in the AiiDA database.
- ``dftb_input`` — SinglefileData (optional): a ready-made ``dftb_in.hsd``,
  copied verbatim. Exactly one of ``parameters`` or ``dftb_input`` is required.
- ``skf_files`` — FolderData (optional): Slater-Koster ``*.skf`` parameter
  files, copied into the working directory via the engine's ``local_copy_list``
  rather than through the sandbox. Omit when ``use_remote_skf_path=True``.
  Ship only the pairs the run needs: a full parameter set is thousands of
  files, and every one of them is copied again for every calculation.
- ``mat_files`` — FolderData (optional): all other files the run needs
  (``geometry.gen``, ``charges.bin``, ...).
- ``structure`` — Dict (optional): metadata (``formula``, ``source_dir``) kept
  for provenance. Not used during DFTB+ execution.

**Outputs**

- ``retrieved`` — FolderData: every file in the retrieve list (provided by
  ``CalcJob`` itself, always present).
- ``output_parameters`` — Dict: scalars parsed from ``detailed.out`` by
  :class:`~aiida_dftbplus.parsers.DftbPlusParser`.

**Exit codes**

===  ============================  =========================================
300  ERROR_MISSING_OUTPUT          ``dftb.out`` or ``detailed.out`` not retrieved
310  ERROR_DFTB_FAILED             DFTB+ reported a fatal error in ``dftb.out``
320  ERROR_SCC_NOT_CONVERGED       SCC cycle did not converge
330  ERROR_GEOMETRY_NOT_CONVERGED  geometry relaxation did not converge
===  ============================  =========================================
"""

from __future__ import annotations

import re

from aiida.common import datastructures
from aiida.engine import CalcJob
from aiida.orm import Bool, Dict, FolderData, SinglefileData


def validate_inputs(inputs, ctx=None):  # pylint: disable=unused-argument
    """Check that exactly one of ``parameters`` / ``dftb_input`` was given.

    Without this the engine would accept a job with neither input and write an
    empty ``dftb_in.hsd``, a mistake DFTB+ only reports once it is already
    running on the remote machine.

    :param inputs: the inputs namespace being validated
    :param ctx: port-namespace context supplied by the engine (unused)
    :returns: an error message when invalid, ``None`` otherwise
    """
    has_parameters = inputs.get("parameters") is not None
    has_dftb_input = inputs.get("dftb_input") is not None

    if has_parameters and has_dftb_input:
        return "Provide either 'parameters' or 'dftb_input', not both."
    if not has_parameters and not has_dftb_input:
        return "One of 'parameters' or 'dftb_input' is required."
    return None


class DftbPlusCalculation(CalcJob):
    """
    AiiDA calculation plugin wrapping the DFTB+ executable.

    Runs one DFTB+ calculation and retrieves all of its output files.
    """

    @classmethod
    def define(cls, spec):
        """Define inputs, outputs and exit codes of the calculation."""
        super().define(spec)

        # ── Inputs ────────────────────────────────────────────────────────
        spec.input(
            "parameters",
            valid_type=Dict,
            required=False,
            help=(
                "Structured DFTB+ input as a nested dict mirroring the HSD block "
                "structure. When present, dftb_in.hsd is generated from it via "
                "_dict_to_hsd(), so every setting is queryable in the database."
            ),
        )
        spec.input(
            "dftb_input",
            valid_type=SinglefileData,
            required=False,
            help=(
                "A ready-made dftb_in.hsd file, copied verbatim. Used instead of "
                "'parameters'. Exactly one of the two is required."
            ),
        )
        spec.input(
            "skf_files",
            valid_type=FolderData,
            required=False,
            help=(
                "FolderData containing the *.skf Slater-Koster parameter files. "
                "Stored once in the database and reused across calculations. "
                "Omit when use_remote_skf_path is True."
            ),
        )
        spec.input(
            "mat_files",
            valid_type=FolderData,
            required=False,
            help=(
                "FolderData containing all other files the run needs "
                "(geometry.gen, charges.bin, ...). Only set it when such files "
                "actually exist — an empty FolderData causes transport errors."
            ),
        )
        spec.input(
            "structure",
            valid_type=Dict,
            required=False,
            help=(
                "Metadata dictionary kept for provenance. Recommended keys: "
                "formula (str), source_dir (str). Not used by DFTB+ itself."
            ),
        )
        spec.input(
            "use_remote_skf_path",
            valid_type=Bool,
            default=lambda: Bool(False),
            help=(
                "If True, keep the absolute SKF path already written in the HSD and "
                "upload no SKF file — the remote machine must hold them at that "
                "path. Avoids shipping thousands of files with every job."
            ),
        )
        spec.input(
            "fix_output_prefix",
            valid_type=Bool,
            default=lambda: Bool(True),
            help="If True, rewrite OutputPrefix = './' to OutputPrefix = 'geom.out'.",
        )

        spec.inputs.validator = validate_inputs

        # ── Outputs ───────────────────────────────────────────────────────
        spec.output(
            "output_parameters",
            valid_type=Dict,
            required=False,
            help=(
                "Scalars parsed from detailed.out: total_energy_H, total_energy_eV, "
                "fermi_energy_eV, scc_converged, n_scc_iterations, forces_eV_Ang "
                "and max_force_eV_Ang."
            ),
        )

        # ── Exit codes ────────────────────────────────────────────────────
        spec.exit_code(
            300,
            "ERROR_MISSING_OUTPUT",
            message="dftb.out or detailed.out was not retrieved from the remote.",
        )
        spec.exit_code(
            310,
            "ERROR_DFTB_FAILED",
            message="DFTB+ reported a fatal ERROR in dftb.out.",
        )
        spec.exit_code(
            320,
            "ERROR_SCC_NOT_CONVERGED",
            message="SCC self-consistency cycle did not converge.",
        )
        spec.exit_code(
            330,
            "ERROR_GEOMETRY_NOT_CONVERGED",
            message="Geometry relaxation did not converge within MaxSteps.",
        )

        # ── Default values for AiiDA options ──────────────────────────────
        spec.inputs["metadata"]["options"]["parser_name"].default = "dftbplus"
        spec.inputs["metadata"]["options"]["resources"].default = {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 1,
        }
        spec.inputs["metadata"]["options"]["max_wallclock_seconds"].default = 7200
        spec.inputs["metadata"]["options"]["withmpi"].default = False

    def prepare_for_submission(self, folder):
        """
        Create input files.

        The steps, in order:

        1. obtain the HSD text — generated from ``parameters``, or read
           verbatim from ``dftb_input``;
        2. patch that text (output prefix, SKF prefix) as the flags request;
        3. write ``dftb_in.hsd`` into the sandbox folder;
        4. hand the ``*.skf`` files to the engine's ``local_copy_list``, unless
           the remote already holds them;
        5. copy the extra material files into the sandbox;
        6. build and return the ``CodeInfo`` + ``CalcInfo``.

        All patching happens on the local HSD string, so no input node is ever
        modified in place.

        **Why the SKF files bypass the sandbox.** Anything written into the
        sandbox is copied twice more by the engine: once into the working
        directory, and once into this calculation's own repository as a record
        of its raw input. For a full Slater-Koster set — several thousand files
        and well over a gigabyte — those two extra passes dominate the job,
        which itself may run in under a second. Putting the ``skf_files`` node
        on ``local_copy_list`` instead lets the engine copy the whole folder in
        one tree operation straight to the working directory. Provenance is
        unaffected: ``skf_files`` is a stored input node, linked to this
        calculation, so the record lives there rather than being duplicated
        per job.

        :param folder: an `aiida.common.folders.Folder` where the plugin should temporarily place all files
            needed by the calculation.
        :return: `aiida.common.datastructures.CalcInfo` instance
        """
        # ── Step 1: obtain the HSD text ───────────────────────────────────
        if "parameters" in self.inputs:
            hsd = self._dict_to_hsd(self.inputs.parameters.get_dict())
        else:
            with self.inputs.dftb_input.open(mode="r") as handle:
                hsd = handle.read()

        # ── Step 2: patch the HSD text ────────────────────────────────────
        upload_skf = "skf_files" in self.inputs and not self.inputs.use_remote_skf_path.value

        if self.inputs.fix_output_prefix.value:
            hsd = self._fix_output_prefix(hsd)
        if upload_skf:
            # The files land next to dftb_in.hsd, so the prefix must point there.
            hsd = self._patch_skf_paths(hsd)

        # ── Step 3: write dftb_in.hsd ─────────────────────────────────────
        with folder.open("dftb_in.hsd", "w") as handle:
            handle.write(hsd)

        # ── Step 4: hand the *.skf files to the engine ────────────────────
        # Source and target are both "." — the whole node, flat into the working
        # directory — so the engine copies the tree once instead of making a
        # round trip per file. The paths must be strings, not None: `presubmit`
        # validates every entry with `validate_list_of_string_tuples` and
        # rejects None, even though the copy itself would accept it.
        local_copy_list = []
        if upload_skf:
            local_copy_list.append((self.inputs.skf_files.uuid, ".", "."))

        # ── Step 5: copy the extra material files ─────────────────────────
        if "mat_files" in self.inputs:
            for name in self.inputs.mat_files.list_object_names():
                # skip dftb_in.hsd — the version written above wins
                if name == "dftb_in.hsd":
                    continue
                with self.inputs.mat_files.open(name, "rb") as src, folder.open(name, "wb") as dst:
                    dst.write(src.read())

        # ── Step 6: CodeInfo — how to invoke the executable ───────────────
        codeinfo = datastructures.CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.stdout_name = "dftb.out"  # redirect stdout → dftb.out
        codeinfo.stderr_name = "dftb.err"  # redirect stderr → dftb.err
        codeinfo.withmpi = self.inputs.metadata.options.withmpi

        # ── CalcInfo — what AiiDA retrieves once the job finishes ─────────
        calcinfo = datastructures.CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.local_copy_list = local_copy_list
        calcinfo.retrieve_list = [
            "dftb.out",  # stdout — checked for fatal errors
            "dftb.err",  # stderr — scheduler and system errors
            "detailed.out",  # main output: energies, forces, charges
            "band.out",  # band structure, when eigenvalues were requested
            "geom.out.gen",  # final geometry after relaxation
            "geom.out.xyz",  # final geometry, xyz format
            "charges.bin",  # converged charges, for restarting
            "dftb_pin.hsd",  # DFTB+ processed input, for debugging
        ]

        return calcinfo

    # ── Private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _patch_skf_paths(hsd: str) -> str:
        """
        Replace absolute SKF directory paths in the HSD text with './'
        so DFTB+ finds the *.skf files in the working directory, where
        AiiDA copies them before running the job.

        Handles the common HSD spellings::

            Prefix = "/absolute/path/"              → Prefix = "./"
            Prefix = '/absolute/path/'              → Prefix = './'
            Prefix = /absolute/path/                → Prefix = ./
            SlaterKosterFiles = "/absolute/path/"   → SlaterKosterFiles = "./"
        """
        hsd = re.sub(r'(Prefix\s*=\s*")[^"]+(")', r"\1./\2", hsd)
        hsd = re.sub(r"(Prefix\s*=\s*')[^']+(')", r"\1./\2", hsd)
        hsd = re.sub(r"(Prefix\s*=\s*)(?![\"'])/\S+", r"\1./", hsd)
        hsd = re.sub(r'(SlaterKosterFiles\s*=\s*")[^"]+(")', r"\1./\2", hsd)
        return hsd

    @staticmethod
    def _fix_output_prefix(hsd: str) -> str:
        """Replace ``OutputPrefix = './'`` with ``OutputPrefix = "geom.out"``.

        A bare ``./`` makes DFTB+ write the relaxed geometry to a path that is
        not a file in the working directory, so nothing is ever retrieved.
        """
        return re.sub(r"(OutputPrefix\s*=\s*)['\"]?\./['\"]?", r'\1"geom.out"', hsd)

    @staticmethod
    def _dict_to_hsd(params: dict, indent: int = 0) -> str:
        """
        Serialise a nested Python dict to DFTB+ HSD text.

        Serialisation rules
        -------------------
        - bool value        → ``Key = Yes`` / ``Key = No``
        - int / float value → ``Key = value``  (floats use %g format)
        - str value         → ``Key = "value"``  (always quoted)
        - flat list         → ``Key = v1 v2 v3``
        - list of lists     → ``Key { one row per line }``
        - empty dict {}     → ``Key {}``
        - single-key dict, inner value is a dict
                            → ``Key = TypeName { ... }``  (named typed block)
        - single-key dict, inner value is a scalar
                            → ``Key { innerKey = value }``  (anonymous block)
        - multi-key dict    → ``Key { ... }``  (anonymous block)
        - dict containing ``_raw`` (and no other key)
                            → block content replaced by raw text verbatim
        - key starting with ``_raw`` (e.g. ``_raw_1``)
                            → value written as a raw line; the key itself is omitted
        - any other key starting with ``_``
                            → skipped (internal metadata)
        """
        lines = []
        pad = "  " * indent
        inner_pad = "  " * (indent + 1)

        for key, value in params.items():
            # ── Internal / raw-passthrough keys ───────────────────────────
            if key.startswith("_raw"):
                # Write the value as a verbatim line at the current indentation
                lines.append(f"{pad}{value}")
                continue
            if key.startswith("_"):
                continue

            # ── Scalar values ─────────────────────────────────────────────
            if isinstance(value, bool):
                # bool is checked before int: it is a subclass of int in Python
                lines.append(f"{pad}{key} = {'Yes' if value else 'No'}")

            elif isinstance(value, str):
                lines.append(f'{pad}{key} = "{value}"')

            elif isinstance(value, int):
                lines.append(f"{pad}{key} = {value}")

            elif isinstance(value, float):
                lines.append(f"{pad}{key} = {value:g}")

            elif isinstance(value, list):
                if value and isinstance(value[0], list):
                    # Matrix: one row per line inside a block
                    lines.append(f"{pad}{key} {{")
                    for row in value:
                        lines.append(inner_pad + " ".join(f"{x:g}" for x in row))
                    lines.append(f"{pad}}}")
                else:
                    # Flat list: space-separated on one line
                    lines.append(f"{pad}{key} = " + " ".join(str(x) for x in value))

            # ── Dict values ───────────────────────────────────────────────
            elif isinstance(value, dict):
                if not value:
                    # Empty block: Key {}
                    lines.append(f"{pad}{key} {{}}")

                elif "_raw" in value and len(value) == 1:
                    # Raw-content anonymous block: Key { <verbatim> }
                    lines.append(f"{pad}{key} {{")
                    for raw_line in value["_raw"].splitlines():
                        lines.append(f"{inner_pad}{raw_line}")
                    lines.append(f"{pad}}}")

                elif len(value) == 1:
                    type_name, inner = next(iter(value.items()))

                    if isinstance(inner, dict):
                        if not inner:
                            # Empty typed block: Key = TypeName {}
                            lines.append(f"{pad}{key} = {type_name} {{}}")

                        elif "_raw" in inner and len(inner) == 1:
                            # Typed block with raw content: Key = TypeName { <verbatim> }
                            lines.append(f"{pad}{key} = {type_name} {{")
                            for raw_line in inner["_raw"].splitlines():
                                lines.append(f"{inner_pad}{raw_line}")
                            lines.append(f"{pad}}}")

                        else:
                            # Named typed block: Key = TypeName { recurse }
                            inner_hsd = DftbPlusCalculation._dict_to_hsd(inner, indent + 1)
                            lines.append(f"{pad}{key} = {type_name} {{")
                            lines.append(inner_hsd)
                            lines.append(f"{pad}}}")
                    else:
                        # Single non-dict entry → anonymous block
                        inner_hsd = DftbPlusCalculation._dict_to_hsd({type_name: inner}, indent + 1)
                        lines.append(f"{pad}{key} {{")
                        lines.append(inner_hsd)
                        lines.append(f"{pad}}}")

                else:
                    # Multi-key dict → anonymous block: Key { ... }
                    inner_hsd = DftbPlusCalculation._dict_to_hsd(value, indent + 1)
                    lines.append(f"{pad}{key} {{")
                    lines.append(inner_hsd)
                    lines.append(f"{pad}}}")

        return "\n".join(lines)
