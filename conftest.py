"""pytest fixtures for simplified testing."""

import pytest

pytest_plugins = ["aiida.manage.tests.pytest_fixtures"]


@pytest.fixture(scope="function", autouse=True)
def clear_database_auto(aiida_profile_clean):  # pylint: disable=unused-argument
    """Automatically clear database in between tests.

    ``aiida_profile_clean`` replaces the ``clear_database`` fixture, which was
    removed in aiida-core 2.x.
    """


@pytest.fixture(scope="function")
def dftbplus_code(aiida_local_code_factory):
    """Get a dftbplus code."""
    return aiida_local_code_factory(executable="dftb+", entry_point="dftbplus")
