"""Convenience helpers for setting up a localhost computer and a DFTB+ code.

Two things, both meant for tests and the bundled examples rather than for
production use:

1. an AiiDA ``localhost`` computer, created on first use with a temporary work
   directory;
2. a ``dftb+`` code on that computer, found on ``PATH``.

For real work, create the computer and code with ``verdi computer setup`` and
``verdi code create`` instead — those are stored deliberately, with a work
directory you chose.

Notes
-----
Point 2 requires the ``dftb+`` executable to be available in the ``PATH`` of the
machine running AiiDA. Unlike the plugin-cutter template this plugin grew from,
DFTB+ is not present on a stock UNIX system — install it first, for example
with ``conda install -c conda-forge dftbplus``.
"""

import shutil
import tempfile

from aiida.common.exceptions import NotExistent
from aiida.orm import Computer, InstalledCode, QueryBuilder

LOCALHOST_NAME = "localhost-test"

executables = {
    "dftbplus": "dftb+",
}


def get_path_to_executable(executable):
    """Find an executable on ``PATH``.

    Parameters
    ----------
    executable : str
        Name of the executable to look for.

    Returns
    -------
    str
        Absolute path to the executable.

    Raises
    ------
    ValueError
        If the executable is not on ``PATH``.
    """
    path = shutil.which(executable)
    if path is None:
        raise ValueError(f"'{executable}' executable not found in PATH.")
    return path


def get_computer(name=LOCALHOST_NAME, workdir=None):
    """Load a localhost computer, creating it on first use.

    Parameters
    ----------
    name : str, default: ``'localhost-test'``
        Label of the computer to load or set up.
    workdir : str, optional
        Work directory for a newly created computer. Defaults to a fresh
        temporary directory. Ignored when the computer already exists.

    Returns
    -------
    aiida.orm.computers.Computer
        A stored, configured computer using the ``core.local`` transport and
        the ``core.direct`` scheduler — that is, jobs run immediately, with no
        queue.
    """

    try:
        computer = Computer.collection.get(label=name)
    except NotExistent:
        if workdir is None:
            workdir = tempfile.mkdtemp()

        computer = Computer(
            label=name,
            description="localhost computer set up by aiida_dftbplus tests",
            hostname=name,
            workdir=workdir,
            transport_type="core.local",
            scheduler_type="core.direct",
        )
        computer.store()
        computer.set_minimum_job_poll_interval(0.0)
        computer.configure()

    return computer


def get_code(entry_point, computer):
    """Load the code for a calculation entry point, creating it on first use.

    Parameters
    ----------
    entry_point : str
        Entry point of the calculation plugin. Only ``'dftbplus'`` is known,
        mapping to the ``dftb+`` executable.
    computer : aiida.orm.computers.Computer
        The computer the code runs on, usually from :func:`get_computer`.

    Returns
    -------
    aiida.orm.nodes.data.code.installed.InstalledCode
        A stored code node.

    Raises
    ------
    KeyError
        If the entry point is not one this helper knows about.
    ValueError
        If the corresponding executable is not on ``PATH``.

    Examples
    --------
    >>> computer = get_computer()                      # doctest: +SKIP
    >>> code = get_code('dftbplus', computer)          # doctest: +SKIP
    """

    try:
        executable = executables[entry_point]
    except KeyError as exc:
        raise KeyError(
            f"Entry point '{entry_point}' not recognized. Allowed values: {list(executables.keys())}"
        ) from exc

    builder = QueryBuilder().append(InstalledCode, filters={"label": executable})
    codes = builder.all(flat=True)
    if codes:
        return codes[0]

    path = get_path_to_executable(executable)
    code = InstalledCode(
        label=executable,
        computer=computer,
        filepath_executable=path,
        default_calc_job_plugin=entry_point,
    )
    return code.store()
