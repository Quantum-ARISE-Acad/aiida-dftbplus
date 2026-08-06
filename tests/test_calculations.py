"""Tests for calculations.

Three layers, in increasing order of what they need to run:

1. the pure static helpers of ``DftbPlusCalculation`` and ``DftbPlusParser`` —
   no AiiDA profile, no database, no DFTB+ binary;
2. ``prepare_for_submission`` against a sandbox folder — needs an AiiDA profile
   (supplied by ``conftest.py``) but no daemon and no DFTB+ binary;
3. one end-to-end run, skipped unless a ``dftb+`` executable is on the PATH.

Sample DFTB+ input and output are inline string constants rather than fixture
files, so the repository layout is unchanged.
"""

import io
import shutil

import pytest
from aiida.common.folders import SandboxFolder
from aiida.common.utils import validate_list_of_string_tuples
from aiida.engine import run_get_node
from aiida.engine.utils import instantiate_process
from aiida.manage import get_manager
from aiida.orm import Bool, Dict, FolderData, InstalledCode, SinglefileData
from aiida.plugins import CalculationFactory
from aiida_dftbplus.calculations import DftbPlusCalculation, validate_inputs
from aiida_dftbplus.parsers import DftbPlusParser

# ── Inline sample data ────────────────────────────────────────────────────────

# A minimal but realistic H2 input, in the dict form the plugin serialises.
H2_PARAMETERS = {
    "Geometry": {
        "GenFormat": {
            "_raw": "2  C\n  H\n     1 1    0.0000000000E+00   0.0000000000E+00   0.0000000000E+00\n"
            "     2 1    0.0000000000E+00   0.0000000000E+00   0.7500000000E+00"
        }
    },
    "Hamiltonian": {
        "DFTB": {
            "SCC": True,
            "MaxSCCIterations": 100,
            "SCCTolerance": 1e-5,
            "_raw_1": 'SlaterKosterFiles = Type2FileNames {\n  Prefix = "/opt/skf/mio-1-1/"\n'
            '  Separator = "-"\n  Suffix = ".skf"\n}',
            "_raw_2": 'MaxAngularMomentum {\n  H = "s"\n}',
        }
    },
    "Options": {},
    "ParserOptions": {"ParserVersion": 12},
}

DETAILED_OUT_SCF = """\
 Total charge:                            0.00000000
 Fermi level:                            -0.2345678901 H          -6.3829 eV
 Band energy:                            -0.7891234567 H         -21.4731 eV
          12 SCC iterations

 Total energy:                           -4.0733851869 H        -110.8425 eV
 Extrapolated to 0:                      -4.0733851869 H        -110.8425 eV

 Total Forces
    1   -0.010000000000    0.000000000000    0.000000000000
    2    0.010000000000    0.000000000000    0.000000000000
"""

# Two geometry steps: the parser must report the second (converged) one.
DETAILED_OUT_GEOMETRY = """\
 Total energy:                           -4.0000000000 H        -108.8455 eV

 Total Forces
    1   -0.100000000000    0.000000000000    0.000000000000
    2    0.100000000000    0.000000000000    0.000000000000

 Total energy:                           -4.0733851869 H        -110.8425 eV

 Total Forces
    1   -0.010000000000    0.000000000000    0.000000000000
    2    0.010000000000    0.000000000000    0.000000000000
"""

STDOUT_OK = """\
Processed input in HSD format written to 'dftb_pin.hsd'
Starting initialization...
Geometry converged
DFTB+ running times                          cpu [s]             wall clock [s]
Total                          =         0.42 (100.0%)          0.44 (100.0%)
"""

# DFTB+ prints ERROR! immediately before the SCC verdict when it exhausts
# MaxSCCIterations — the exact shape that must NOT be read as a fatal 310.
STDOUT_SCC_FAILED = """\
Starting initialization...
ERROR!
-> SCC is NOT converged, maximal SCC iterations exceeded
"""

STDOUT_GEOMETRY_FAILED = """\
Starting initialization...
Geometry did not converge!
"""

STDOUT_FATAL = """\
Starting initialization...
ERROR!
-> Unknown keyword in HSD input: 'Hamiltoniann'
"""


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_dftbplus_code(aiida_localhost):
    """A DFTB+ code node pointing at a stand-in executable.

    ``prepare_for_submission`` never runs the binary, so this lets the sandbox
    tests work on a machine without DFTB+ installed.
    """
    return InstalledCode(
        label="dftbplus-fake",
        computer=aiida_localhost,
        filepath_executable="/bin/true",
        default_calc_job_plugin="dftbplus",
    ).store()


def _skf_folder():
    """FolderData holding two dummy Slater-Koster files."""
    folder = FolderData()
    for name in ("H-H.skf", "C-H.skf"):
        folder.put_object_from_filelike(io.StringIO("dummy skf content\n"), name)
    return folder


def _instantiate(**inputs):
    """Instantiate a DftbPlusCalculation process without submitting it."""
    runner = get_manager().get_runner()
    return instantiate_process(runner, DftbPlusCalculation, **inputs)


# ── Layer 1: _dict_to_hsd (no AiiDA profile needed) ───────────────────────────


def test_hsd_bools_serialise_as_yes_no():
    """DFTB+ rejects Python's True/False spelling."""
    hsd = DftbPlusCalculation._dict_to_hsd({"SCC": True, "ReadInitialCharges": False})

    assert "SCC = Yes" in hsd
    assert "ReadInitialCharges = No" in hsd
    assert "True" not in hsd
    assert "False" not in hsd


def test_hsd_scalar_formats():
    """Strings are quoted, ints are bare, floats use %g."""
    hsd = DftbPlusCalculation._dict_to_hsd({"Prefix": "/opt/skf/", "MaxSCCIterations": 250, "SCCTolerance": 1e-5})

    assert 'Prefix = "/opt/skf/"' in hsd
    assert "MaxSCCIterations = 250" in hsd
    assert "SCCTolerance = 1e-05" in hsd


def test_hsd_block_forms():
    """Empty, typed, and anonymous blocks each get their own spelling."""
    hsd = DftbPlusCalculation._dict_to_hsd(
        {
            "Options": {},
            "Optimizer": {"Rational": {}},
            "Filling": {"Fermi": {"Temperature [K]": 300}},
            "Analysis": {"PrintForces": True, "CalculateForces": True},
        }
    )

    assert "Options {}" in hsd
    assert "Optimizer = Rational {}" in hsd
    assert "Filling = Fermi {" in hsd
    assert "Temperature [K] = 300" in hsd
    assert "Analysis {" in hsd


def test_hsd_raw_passthrough_is_verbatim():
    """_raw block content and _raw_* lines survive serialisation unchanged."""
    hsd = DftbPlusCalculation._dict_to_hsd(
        {
            "Geometry": {"GenFormat": {"_raw": "2 C\n  H\n  1 1 0.0 0.0 0.0"}},
            "_raw_1": "Analysis { PrintForces = Yes }",
        }
    )

    assert "Geometry = GenFormat {" in hsd
    assert "1 1 0.0 0.0 0.0" in hsd
    # the _raw_1 key itself is dropped, its value written as a line
    assert "Analysis { PrintForces = Yes }" in hsd
    assert "_raw_1" not in hsd


def test_hsd_skips_internal_keys():
    """Keys starting with '_' are metadata and never reach the HSD file."""
    hsd = DftbPlusCalculation._dict_to_hsd({"SCC": True, "_healing": {"history": ["x"]}})

    assert "SCC = Yes" in hsd
    assert "_healing" not in hsd
    assert "history" not in hsd


def test_hsd_lists():
    """Flat lists go on one line; nested lists become a block of rows."""
    hsd = DftbPlusCalculation._dict_to_hsd({"KPoints": [4, 4, 4], "Lattice": [[1.0, 0.0], [0.0, 1.0]]})

    assert "KPoints = 4 4 4" in hsd
    assert "Lattice {" in hsd
    assert "1 0" in hsd


def test_hsd_round_trip_of_full_input():
    """The realistic H2 input serialises to something DFTB+ would accept."""
    hsd = DftbPlusCalculation._dict_to_hsd(H2_PARAMETERS)

    assert "Geometry = GenFormat {" in hsd
    assert "Hamiltonian = DFTB {" in hsd
    assert "SCC = Yes" in hsd
    assert 'Prefix = "/opt/skf/mio-1-1/"' in hsd
    assert "ParserOptions {" in hsd
    assert hsd.count("{") == hsd.count("}")


# ── Layer 1: HSD patchers ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "line",
    [
        'Prefix = "/opt/skf/mio-1-1/"',
        "Prefix = '/opt/skf/mio-1-1/'",
        "Prefix = /opt/skf/mio-1-1/",
        'SlaterKosterFiles = "/opt/skf/mio-1-1/"',
    ],
)
def test_patch_skf_paths(line):
    """Every quoting form of an absolute SKF path collapses to './'."""
    patched = DftbPlusCalculation._patch_skf_paths(line)

    assert "/opt/skf" not in patched
    assert "./" in patched


def test_fix_output_prefix():
    """A bare './' output prefix becomes a real filename."""
    assert 'OutputPrefix = "geom.out"' in DftbPlusCalculation._fix_output_prefix('OutputPrefix = "./"')
    assert 'OutputPrefix = "geom.out"' in DftbPlusCalculation._fix_output_prefix("OutputPrefix = ./")
    # an already-meaningful prefix is left alone
    assert DftbPlusCalculation._fix_output_prefix('OutputPrefix = "relaxed"') == 'OutputPrefix = "relaxed"'


# ── Layer 1: exit-code detection ──────────────────────────────────────────────


def test_detect_scc_failure_wins_over_generic_error():
    """The regression that matters.

    DFTB+ prints ERROR! on the line immediately before the SCC verdict. If the
    generic ERROR! guard were checked first, every recoverable SCC failure
    would be reported as a fatal 310.
    """
    assert "ERROR!" in STDOUT_SCC_FAILED  # the trap is really present
    assert DftbPlusParser._detect_exit_code(STDOUT_SCC_FAILED, "") == 320


def test_detect_geometry_failure():
    assert DftbPlusParser._detect_exit_code(STDOUT_GEOMETRY_FAILED, "") == 330


def test_detect_generic_fatal_error():
    assert DftbPlusParser._detect_exit_code(STDOUT_FATAL, "") == 310


def test_detect_empty_stdout():
    """No output at all means the process died before writing anything."""
    assert DftbPlusParser._detect_exit_code("", "") == 310
    assert DftbPlusParser._detect_exit_code("   \n  \n", "") == 310


def test_detect_clean_run():
    assert DftbPlusParser._detect_exit_code(STDOUT_OK, DETAILED_OUT_SCF) == 0


# ── Layer 1: detailed.out parsing ─────────────────────────────────────────────


def test_parse_detailed_scalars():
    parsed = DftbPlusParser._parse_detailed(DETAILED_OUT_SCF)

    assert parsed["total_energy_H"] == pytest.approx(-4.0733851869)
    assert parsed["total_energy_eV"] == pytest.approx(-110.8425, abs=1e-3)
    assert parsed["fermi_energy_eV"] == pytest.approx(-6.3829, abs=1e-3)
    assert parsed["n_scc_iterations"] == 12
    assert parsed["scc_converged"] is True


def test_parse_detailed_forces_are_converted():
    """Forces are reported in eV/Å, not the Ha/Bohr of the file."""
    parsed = DftbPlusParser._parse_detailed(DETAILED_OUT_SCF)

    assert len(parsed["forces_eV_Ang"]) == 2
    assert parsed["forces_eV_Ang"][0][0] == pytest.approx(-0.5142206748)
    assert parsed["max_force_eV_Ang"] == pytest.approx(0.5142206748)


def test_parse_detailed_last_block_wins():
    """A geometry optimisation writes one block per step; the last is the result."""
    parsed = DftbPlusParser._parse_detailed(DETAILED_OUT_GEOMETRY)

    assert parsed["total_energy_H"] == pytest.approx(-4.0733851869)
    assert len(parsed["forces_eV_Ang"]) == 2
    assert parsed["max_force_eV_Ang"] == pytest.approx(0.5142206748)


def test_parse_detailed_scc_not_converged_inverts():
    """The file states the negative case, the output parameter states the positive."""
    parsed = DftbPlusParser._parse_detailed("SCC is NOT converged, maximal SCC iterations exceeded")

    assert parsed["scc_converged"] is False


# ── Layer 1: input validation ─────────────────────────────────────────────────


def test_validate_inputs_requires_one_source():
    assert "required" in validate_inputs({})
    assert "not both" in validate_inputs({"parameters": object(), "dftb_input": object()})
    assert validate_inputs({"parameters": object()}) is None
    assert validate_inputs({"dftb_input": object()}) is None


# ── Layer 2: prepare_for_submission (AiiDA profile, no daemon, no binary) ─────


def test_prepare_writes_hsd_from_parameters(fake_dftbplus_code):
    """The parameters Dict is serialised into dftb_in.hsd in the sandbox."""
    process = _instantiate(code=fake_dftbplus_code, parameters=Dict(H2_PARAMETERS))

    with SandboxFolder() as folder:
        process.prepare_for_submission(folder)

        assert "dftb_in.hsd" in folder.get_content_list()
        with folder.open("dftb_in.hsd", "r") as handle:
            hsd = handle.read()

    assert "Hamiltonian = DFTB {" in hsd
    assert "SCC = Yes" in hsd


def test_prepare_copies_raw_dftb_input_verbatim(fake_dftbplus_code):
    """A ready-made dftb_in.hsd is used as-is."""
    raw = "Geometry = GenFormat {\n2 C\n}\nHamiltonian = DFTB {\n  SCC = Yes\n}\n"
    process = _instantiate(
        code=fake_dftbplus_code,
        dftb_input=SinglefileData(io.StringIO(raw), filename="dftb_in.hsd"),
    )

    with SandboxFolder() as folder:
        process.prepare_for_submission(folder)
        with folder.open("dftb_in.hsd", "r") as handle:
            hsd = handle.read()

    assert hsd == raw


def test_prepare_retrieve_list_covers_all_outputs(fake_dftbplus_code):
    """Every file DFTB+ can produce is retrieved."""
    process = _instantiate(code=fake_dftbplus_code, parameters=Dict(H2_PARAMETERS))

    with SandboxFolder() as folder:
        calcinfo = process.prepare_for_submission(folder)

    assert set(calcinfo.retrieve_list) == {
        "dftb.out",
        "dftb.err",
        "detailed.out",
        "band.out",
        "geom.out.gen",
        "geom.out.xyz",
        "charges.bin",
        "dftb_pin.hsd",
    }
    codeinfo = calcinfo.codes_info[0]
    assert codeinfo.stdout_name == "dftb.out"
    assert codeinfo.stderr_name == "dftb.err"


def test_prepare_uploads_skf_and_patches_prefix(fake_dftbplus_code):
    """With local SKF files, the folder is queued for copy and the prefix points at it."""
    skf_files = _skf_folder()
    process = _instantiate(
        code=fake_dftbplus_code,
        parameters=Dict(H2_PARAMETERS),
        skf_files=skf_files,
    )

    with SandboxFolder() as folder:
        calcinfo = process.prepare_for_submission(folder)
        contents = folder.get_content_list()
        with folder.open("dftb_in.hsd", "r") as handle:
            hsd = handle.read()

    # The whole node goes on the local_copy_list, flat into the working
    # directory — it must never be staged through the sandbox, which the
    # engine would then duplicate into this calculation's own repository.
    assert calcinfo.local_copy_list == [(skf_files.uuid, ".", ".")]
    # The engine runs this check in `presubmit` before any file is copied, and
    # it rejects None paths — so assert the entries survive it.
    validate_list_of_string_tuples(calcinfo.local_copy_list, tuple_length=3)
    assert "H-H.skf" not in contents
    assert "C-H.skf" not in contents
    assert 'Prefix = "./"' in hsd
    assert "/opt/skf" not in hsd


def test_prepare_skips_skf_upload_when_remote(fake_dftbplus_code):
    """use_remote_skf_path keeps the absolute path and ships nothing."""
    process = _instantiate(
        code=fake_dftbplus_code,
        parameters=Dict(H2_PARAMETERS),
        skf_files=_skf_folder(),
        use_remote_skf_path=Bool(True),
    )

    with SandboxFolder() as folder:
        calcinfo = process.prepare_for_submission(folder)
        contents = folder.get_content_list()
        with folder.open("dftb_in.hsd", "r") as handle:
            hsd = handle.read()

    assert calcinfo.local_copy_list == []
    assert "H-H.skf" not in contents
    assert 'Prefix = "/opt/skf/mio-1-1/"' in hsd


def test_prepare_copies_mat_files_but_not_their_hsd(fake_dftbplus_code):
    """Extra material files ride along; a stale dftb_in.hsd among them is ignored."""
    mat_files = FolderData()
    mat_files.put_object_from_filelike(io.StringIO("2 C\n  H\n"), "geometry.gen")
    mat_files.put_object_from_filelike(io.StringIO("STALE INPUT"), "dftb_in.hsd")

    process = _instantiate(
        code=fake_dftbplus_code,
        parameters=Dict(H2_PARAMETERS),
        mat_files=mat_files,
    )

    with SandboxFolder() as folder:
        process.prepare_for_submission(folder)
        contents = folder.get_content_list()
        with folder.open("dftb_in.hsd", "r") as handle:
            hsd = handle.read()

    assert "geometry.gen" in contents
    assert "STALE INPUT" not in hsd
    assert "Hamiltonian = DFTB {" in hsd


def test_prepare_does_not_mutate_input_node(fake_dftbplus_code):
    """Patching happens on the local string, never on the stored node."""
    parameters = Dict(H2_PARAMETERS)
    process = _instantiate(code=fake_dftbplus_code, parameters=parameters, skf_files=_skf_folder())

    with SandboxFolder() as folder:
        process.prepare_for_submission(folder)

    raw_block = parameters.get_dict()["Hamiltonian"]["DFTB"]["_raw_1"]
    assert "/opt/skf/mio-1-1/" in raw_block


def test_missing_input_source_is_rejected(fake_dftbplus_code):
    """Neither parameters nor dftb_input must fail before anything is submitted."""
    with pytest.raises(ValueError, match="required"):
        _instantiate(code=fake_dftbplus_code)


def test_both_input_sources_are_rejected(fake_dftbplus_code):
    with pytest.raises(ValueError, match="not both"):
        _instantiate(
            code=fake_dftbplus_code,
            parameters=Dict(H2_PARAMETERS),
            dftb_input=SinglefileData(io.StringIO("Geometry {}"), filename="dftb_in.hsd"),
        )


# ── Layer 3: end-to-end (needs a real DFTB+ binary) ───────────────────────────


@pytest.mark.skipif(shutil.which("dftb+") is None, reason="dftb+ executable not found in PATH")
def test_process(dftbplus_code):
    """Run a real DFTB+ calculation and check the outputs come back.

    The input is deliberately broken (no Slater-Koster files are shipped), so
    DFTB+ fails — but that still exercises the whole path: sandbox assembly,
    submission, retrieval, and parser classification. What is asserted is that
    the plugin reported a DFTB+-shaped failure rather than crashing.
    """
    inputs = {
        "code": dftbplus_code,
        "parameters": Dict(H2_PARAMETERS),
        "metadata": {"options": {"max_wallclock_seconds": 60, "withmpi": False}},
    }

    _, node = run_get_node(CalculationFactory("dftbplus"), **inputs)

    assert node.is_finished
    assert "retrieved" in node.outputs
    assert "dftb.out" in node.outputs.retrieved.list_object_names()
    assert node.exit_status in (0, 300, 310, 320, 330)
