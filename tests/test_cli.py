"""Tests for command line interface."""

import pytest
from aiida.plugins import DataFactory
from click.testing import CliRunner
from voluptuous import Invalid

from aiida_dftbplus.cli import export, hsd, list_

PARAMETERS = {
    "Geometry": {"GenFormat": {"_raw": "2  C\n  H\n  1 1 0.0 0.0 0.0"}},
    "Hamiltonian": {"DFTB": {"SCC": True, "MaxSCCIterations": 100}},
}


# pylint: disable=attribute-defined-outside-init
class TestDataCli:
    """Test verdi data cli plugin."""

    def setup_method(self):
        """Prepare nodes for cli tests."""
        dftb_parameters = DataFactory("dftbplus")
        self.parameters = dftb_parameters(PARAMETERS)
        self.parameters.store()
        self.runner = CliRunner()

    def test_data_dftbplus_list(self):
        """Test 'verdi data dftbplus list'

        Tests that it can be reached and that it lists the node we have set up.
        """
        result = self.runner.invoke(list_, catch_exceptions=False)
        assert str(self.parameters.pk) in result.output

    def test_data_dftbplus_export(self):
        """Test 'verdi data dftbplus export'

        Tests that it can be reached and that it shows the contents of the node
        we have set up.
        """
        result = self.runner.invoke(export, [str(self.parameters.pk)], catch_exceptions=False)
        assert "Hamiltonian" in result.output
        assert "MaxSCCIterations" in result.output

    def test_data_dftbplus_hsd(self):
        """Test 'verdi data dftbplus hsd'

        Tests that the node is rendered as the HSD file it would produce.
        """
        result = self.runner.invoke(hsd, [str(self.parameters.pk)], catch_exceptions=False)
        assert "Hamiltonian = DFTB {" in result.output
        assert "SCC = Yes" in result.output
        # the raw geometry block is passed through verbatim
        assert "1 1 0.0 0.0 0.0" in result.output


class TestDftbParameters:
    """Test the DftbParameters data class itself."""

    def test_known_blocks_are_accepted(self):
        dftb_parameters = DataFactory("dftbplus")
        node = dftb_parameters(PARAMETERS)

        assert node.get_dict()["Hamiltonian"]["DFTB"]["SCC"] is True

    def test_unknown_top_level_block_is_rejected(self):
        """A typo at the top level is caught here rather than by DFTB+ on the remote."""
        dftb_parameters = DataFactory("dftbplus")

        with pytest.raises(Invalid, match="Hamiltoniann"):
            dftb_parameters({"Hamiltoniann": {"DFTB": {"SCC": True}}})

    def test_underscore_keys_are_passed_through(self):
        """_raw* passthrough and _-prefixed metadata bypass the block-name check."""
        dftb_parameters = DataFactory("dftbplus")
        node = dftb_parameters({"_raw_1": "Analysis { PrintForces = Yes }", "_origin": "test"})

        assert node.get_dict()["_raw_1"] == "Analysis { PrintForces = Yes }"

    def test_get_hsd(self):
        dftb_parameters = DataFactory("dftbplus")
        node = dftb_parameters(PARAMETERS)

        rendered = node.get_hsd()

        assert "Hamiltonian = DFTB {" in rendered
        assert "SCC = Yes" in rendered
        assert "MaxSCCIterations = 100" in rendered
