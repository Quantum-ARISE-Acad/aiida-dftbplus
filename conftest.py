"""pytest fixtures for simplified testing."""

import pytest

pytest_plugins = ["aiida.tools.pytest_fixtures"]


@pytest.fixture(scope="function", autouse=True)
def clear_database_auto(aiida_profile_clean):  # pylint: disable=unused-argument
    """Automatically clear database in between tests.

    ``aiida_profile_clean`` replaces the ``clear_database`` fixture, which was
    removed in aiida-core 2.x.
    """


@pytest.fixture(scope="function")
def dftbplus_code(aiida_code_installed):
    """Get a dftbplus code."""
    return aiida_code_installed(filepath_executable="dftb+", default_calc_job_plugin="dftbplus")
