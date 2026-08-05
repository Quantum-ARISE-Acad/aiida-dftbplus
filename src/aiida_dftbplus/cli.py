"""
Command line interface (cli) for aiida_dftbplus.

Register new commands either via the "console_scripts" entry point or plug them
directly into the 'verdi' command by using AiiDA-specific entry points like
"aiida.cmdline.data" (both in the pyproject.toml file).
"""

import sys

import click
from aiida.cmdline.commands.cmd_data import verdi_data
from aiida.cmdline.params.types import DataParamType
from aiida.cmdline.utils import decorators
from aiida.orm import QueryBuilder
from aiida.plugins import DataFactory


def _write_or_echo(string, outfile):
    """Write ``string`` to ``outfile``, or print it when no file was given."""
    if outfile:
        with open(outfile, "w", encoding="utf8") as handle:
            handle.write(string)
    else:
        click.echo(string)


# See aiida.cmdline.data entry point in pyproject.toml
@verdi_data.group("dftbplus")
def data_cli():
    """Command line interface for aiida-dftbplus"""


@data_cli.command("list")
@decorators.with_dbenv()
def list_():  # pylint: disable=redefined-builtin
    """
    Display all DftbParameters nodes
    """
    dftb_parameters = DataFactory("dftbplus")

    qb = QueryBuilder()
    qb.append(dftb_parameters)
    results = qb.all()

    s = ""
    for result in results:
        obj = result[0]
        s += f"{obj!s}, pk: {obj.pk}\n"
    sys.stdout.write(s)


@data_cli.command("export")
@click.argument("node", metavar="IDENTIFIER", type=DataParamType())
@click.option(
    "--outfile",
    "-o",
    type=click.Path(dir_okay=False),
    help="Write output to file (default: print to stdout).",
)
@decorators.with_dbenv()
def export(node, outfile):
    """Export a DftbParameters node (identified by PK, UUID or label) to plain text."""
    _write_or_echo(str(node), outfile)


@data_cli.command("hsd")
@click.argument("node", metavar="IDENTIFIER", type=DataParamType())
@click.option(
    "--outfile",
    "-o",
    type=click.Path(dir_okay=False),
    help="Write output to file (default: print to stdout).",
)
@decorators.with_dbenv()
def hsd(node, outfile):
    """Render a DftbParameters node as the dftb_in.hsd file it produces.

    Shows exactly what the calculation would write, so an input can be checked
    by eye before it is submitted.
    """
    if not hasattr(node, "get_hsd"):
        raise click.ClickException(f"Node <{node.pk}> is a {type(node).__name__}, not a DftbParameters node.")
    _write_or_echo(node.get_hsd(), outfile)
