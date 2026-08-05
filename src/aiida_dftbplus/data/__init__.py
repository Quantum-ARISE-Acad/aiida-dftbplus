"""Data types provided by plugin

Register data types via the "aiida.data" entry point in pyproject.toml.
"""

# You can directly use or subclass aiida.orm.data.Data
# or any other data type listed under 'verdi data'
from aiida.orm import Dict
from voluptuous import Invalid, Schema

from aiida_dftbplus.calculations import DftbPlusCalculation

# The top-level blocks a dftb_in.hsd file may contain. Anything else at the top
# level is almost certainly a typo — and a typo there is expensive, because
# DFTB+ only reports it once the job is already running on the remote machine.
KNOWN_TOP_LEVEL_BLOCKS = frozenset(
    {
        "Analysis",
        "Driver",
        "ElectronDynamics",
        "ExcitedState",
        "Geometry",
        "Hamiltonian",
        "Options",
        "Parallel",
        "ParserOptions",
        "Reks",
        "Transport",
    }
)


def hsd_block_name(key):
    """Validate one top-level key of a DFTB+ parameter dictionary.

    Accepts the documented HSD blocks, plus any key starting with ``_``:
    ``_raw*`` keys are written to the HSD file verbatim, and other
    ``_``-prefixed keys are metadata that never reaches the file at all.

    :param key: the dictionary key to validate
    :returns: the key, unchanged, when it is acceptable
    :raises voluptuous.Invalid: when the key is not a known block
    """
    if not isinstance(key, str):
        raise Invalid(f"HSD block names must be strings, got {key!r}")
    if key.startswith("_"):
        return key
    if key not in KNOWN_TOP_LEVEL_BLOCKS:
        raise Invalid(
            f"'{key}' is not a known top-level DFTB+ block. "
            f"Allowed: {', '.join(sorted(KNOWN_TOP_LEVEL_BLOCKS))}. "
            "Prefix a key with '_raw' to pass it through to the HSD verbatim."
        )
    return key


class DftbParameters(Dict):  # pylint: disable=too-many-ancestors
    """
    DFTB+ input parameters.

    This class represents a nested python dictionary mirroring the block
    structure of ``dftb_in.hsd``, which
    :class:`~aiida_dftbplus.calculations.DftbPlusCalculation` serialises into
    the input file. Storing the settings as a dictionary rather than as an
    opaque file makes every DFTB+ parameter queryable in the AiiDA database.

    Usage::

        DftbParameters = DataFactory('dftbplus')
        parameters = DftbParameters({
            'Geometry': {'GenFormat': {'_raw': '...'}},
            'Hamiltonian': {'DFTB': {'SCC': True, 'MaxSCCIterations': 100}},
        })
    """

    # "voluptuous" schema  to add automatic validation
    schema = Schema({hsd_block_name: object})

    # pylint: disable=redefined-builtin
    def __init__(self, dict=None, **kwargs):
        """
        Constructor for the data class

        Usage: ``DftbParameters(dict={'Hamiltonian': {'DFTB': {'SCC': True}}})``

        :param parameters_dict: dictionary of DFTB+ input blocks
        :param type parameters_dict: dict

        """
        dict = self.validate(dict)
        super().__init__(dict=dict, **kwargs)

    def validate(self, parameters_dict):
        """Validate the top-level DFTB+ blocks.

        Uses the voluptuous package for validation. Find out about allowed keys using::

            print(DftbParameters.schema.schema)

        Only the top level is checked: the contents of each block are passed
        straight to DFTB+, whose own parser is the authority on them.

        :param parameters_dict: dictionary of DFTB+ input blocks
        :param type parameters_dict: dict
        :returns: validated dictionary
        """
        return DftbParameters.schema(parameters_dict)

    def get_hsd(self):
        """Render these parameters as DFTB+ HSD text.

        Returns exactly what
        :meth:`~aiida_dftbplus.calculations.DftbPlusCalculation.prepare_for_submission`
        would write to ``dftb_in.hsd``, before the optional path patches. Useful
        for checking an input by eye before submitting it.

        :returns: the HSD representation of this node
        :rtype: str
        """
        return DftbPlusCalculation._dict_to_hsd(self.get_dict())

    def __str__(self):
        """String representation of node.

        Append values of dictionary to usual representation. E.g.::

            uuid: b416cbee-24e8-47a8-8c11-6d668770158b (pk: 590)
            {'Hamiltonian': {'DFTB': {'SCC': True}}}

        """
        string = super().__str__()
        string += "\n" + str(self.get_dict())
        return string
