#!/usr/bin/env python
"""Run a test DFTB+ calculation on localhost.

Usage: ./example_01.py [--code <label>] [--skf-dir <path>]
"""

import copy
from os import path

import click
from aiida import cmdline, engine, orm
from aiida.plugins import CalculationFactory
from aiida_dftbplus import helpers
from aiida_dftbplus.calculations import DftbPlusCalculation

INPUT_DIR = path.join(path.dirname(path.realpath(__file__)), "input_files")

# A minimal H2 calculation, expressed as the nested dict the plugin serialises
# into dftb_in.hsd. Blocks the plugin does not need to understand are passed
# through verbatim under "_raw_*" keys.
PARAMETERS = {
    "Geometry": {
        "GenFormat": {
            "_raw": (
                "2  C\n"
                "  H\n"
                "     1 1    0.0000000000E+00   0.0000000000E+00   0.0000000000E+00\n"
                "     2 1    0.0000000000E+00   0.0000000000E+00   0.7500000000E+00"
            )
        }
    },
    "Hamiltonian": {
        "DFTB": {
            "SCC": True,
            "MaxSCCIterations": 100,
            "SCCTolerance": 1e-5,
            "_raw_1": (
                'SlaterKosterFiles = Type2FileNames {\n  Prefix = "SKF_PREFIX"\n  Separator = "-"\n  Suffix = ".skf"\n}'
            ),
            "_raw_2": 'MaxAngularMomentum {\n  H = "s"\n}',
        }
    },
    "Options": {},
    "Analysis": {"CalculateForces": True},
    "ParserOptions": {"ParserVersion": 12},
}


def build_parameters(skf_dir):
    """Return the parameter dict with the Slater-Koster prefix filled in."""
    parameters = copy.deepcopy(PARAMETERS)
    dftb = parameters["Hamiltonian"]["DFTB"]
    dftb["_raw_1"] = dftb["_raw_1"].replace("SKF_PREFIX", skf_dir)
    return parameters


def run_example(dftbplus_code, skf_dir):
    """Run a calculation on the localhost computer.

    Uses test helpers to create AiiDA Code on the fly.
    """
    if not dftbplus_code:
        # get code
        computer = helpers.get_computer()
        dftbplus_code = helpers.get_code(entry_point="dftbplus", computer=computer)

    # Prepare input parameters
    parameters = orm.Dict(build_parameters(skf_dir))

    # Show what the plugin will actually write to dftb_in.hsd
    print("Generated dftb_in.hsd:")
    print(DftbPlusCalculation._dict_to_hsd(parameters.get_dict()))
    print()

    # set up calculation
    inputs = {
        "code": dftbplus_code,
        "parameters": parameters,
        # the Slater-Koster files already sit at skf_dir on this machine,
        # so keep the absolute path and upload nothing
        "use_remote_skf_path": orm.Bool(True),
        "structure": orm.Dict({"formula": "H2", "source_dir": INPUT_DIR}),
        "metadata": {
            "description": "Test job submission with the aiida_dftbplus plugin",
            "options": {"max_wallclock_seconds": 600, "withmpi": False},
        },
    }

    # Note: in order to submit your calculation to the aiida daemon, do:
    # from aiida.engine import submit
    # future = submit(CalculationFactory('dftbplus'), **inputs)
    result, node = engine.run_get_node(CalculationFactory("dftbplus"), **inputs)

    print(f"Calculation finished with exit status {node.exit_status}")
    print(f"Retrieved files: {node.outputs.retrieved.list_object_names()}")

    if "output_parameters" in result:
        for key, value in result["output_parameters"].get_dict().items():
            print(f"  {key}: {value}")
    else:
        print("No output_parameters — check 'verdi process report' for the reason.")


@click.command()
@cmdline.utils.decorators.with_dbenv()
@cmdline.params.options.CODE()
@click.option(
    "--skf-dir",
    default="/opt/skf/mio-1-1/",
    show_default=True,
    help="Directory holding the Slater-Koster *.skf files on this machine.",
)
def cli(code, skf_dir):
    """Run example.

    Example usage: $ ./example_01.py --code dftb+@localhost --skf-dir /opt/skf/mio-1-1/

    Alternative (creates dftb+@localhost-test code): $ ./example_01.py

    Help: $ ./example_01.py --help
    """
    run_example(code, skf_dir)


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
