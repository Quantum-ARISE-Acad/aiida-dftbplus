"""Data types provided by ``aiida_dftbplus``.

Registered with AiiDA through the ``aiida.data`` entry point in
``pyproject.toml``, under the name ``dftbplus``, so the class is reachable as
``DataFactory('dftbplus')``.

The module contains one node type, :class:`DftbParameters`, and the validation
callback it is built from, :func:`hsd_block_name`. The validation is
deliberately shallow — it checks the top-level block names and nothing else.
The contents of each block go straight to DFTB+, whose own parser is the
authority on them.
"""

from aiida.orm import Dict
from voluptuous import Invalid, Schema

from aiida_dftbplus.calculations import DftbPlusCalculation

#: The top-level blocks a ``dftb_in.hsd`` file may contain. Anything else at the
#: top level is almost certainly a typo — and a typo there is expensive, because
#: DFTB+ only reports it once the job is already running on the remote machine.
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

    Parameters
    ----------
    key : str
        The dictionary key to validate.

    Returns
    -------
    str
        The key, unchanged, when it is acceptable.

    Raises
    ------
    voluptuous.Invalid
        When the key is neither a known top-level block nor ``_``-prefixed.

    Examples
    --------
    >>> hsd_block_name('Hamiltonian')
    'Hamiltonian'
    >>> hsd_block_name('_raw_1')
    '_raw_1'
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
    """DFTB+ input parameters, validated at construction.

    A nested Python dictionary mirroring the block structure of
    ``dftb_in.hsd``, which
    :class:`~aiida_dftbplus.calculations.DftbPlusCalculation` serialises into
    the input file. Storing the settings as a dictionary rather than as an
    opaque file is what makes every DFTB+ parameter queryable in the AiiDA
    database.

    Using this class instead of a plain :class:`~aiida.orm.nodes.data.dict.Dict`
    buys one thing: a misspelled top-level block is caught here, in Python,
    instead of by DFTB+ minutes later on a remote machine.

    Examples
    --------
    >>> from aiida.plugins import DataFactory
    >>> DftbParameters = DataFactory('dftbplus')
    >>> parameters = DftbParameters({
    ...     'Hamiltonian': {'DFTB': {'SCC': True, 'MaxSCCIterations': 100}},
    ... })
    >>> print(parameters.get_hsd())
    Hamiltonian = DFTB {
      SCC = Yes
      MaxSCCIterations = 100
    }

    A typo is rejected immediately::

        >>> DftbParameters({'Hamiltoniann': {}})
        Traceback (most recent call last):
        ...
        voluptuous.error.MultipleInvalid: 'Hamiltoniann' is not a known top-level DFTB+ block. ...

    See Also
    --------
    aiida_dftbplus.data.KNOWN_TOP_LEVEL_BLOCKS : the blocks this class accepts.
    """

    #: Voluptuous schema applied by :meth:`validate` on construction.
    schema = Schema({hsd_block_name: object})

    # pylint: disable=redefined-builtin
    def __init__(self, dict=None, **kwargs):
        """Construct and validate the node.

        Parameters
        ----------
        dict : dict, optional
            Dictionary of DFTB+ input blocks. Named ``dict`` to match the
            signature of :class:`~aiida.orm.nodes.data.dict.Dict`.
        **kwargs
            Forwarded to :class:`~aiida.orm.nodes.data.dict.Dict`.

        Raises
        ------
        voluptuous.Invalid
            If any top-level key is not a known DFTB+ block.
        """
        dict = self.validate(dict)
        super().__init__(dict=dict, **kwargs)

    def validate(self, parameters_dict):
        """Validate the top-level DFTB+ blocks.

        Only the top level is checked: the contents of each block are passed
        straight to DFTB+, whose own parser is the authority on them. List the
        allowed keys with ``print(DftbParameters.schema.schema)``.

        Parameters
        ----------
        parameters_dict : dict
            Dictionary of DFTB+ input blocks.

        Returns
        -------
        dict
            The validated dictionary.

        Raises
        ------
        voluptuous.Invalid
            If a top-level key is not a known block.
        """
        return DftbParameters.schema(parameters_dict)

    def get_hsd(self):
        """Render these parameters as DFTB+ HSD text.

        Returns exactly what
        :meth:`~aiida_dftbplus.calculations.DftbPlusCalculation.prepare_for_submission`
        would write to ``dftb_in.hsd``, *before* the optional path patches
        (``fix_output_prefix`` and the Slater-Koster prefix rewrite). Useful for
        checking an input by eye before submitting it, and what
        ``verdi data dftbplus hsd <PK>`` prints.

        Returns
        -------
        str
            The HSD representation of this node.
        """
        return DftbPlusCalculation._dict_to_hsd(self.get_dict())

    def __str__(self):
        """Return the node's usual representation plus its dictionary.

        Returns
        -------
        str
            For example::

                uuid: b416cbee-24e8-47a8-8c11-6d668770158b (pk: 590)
                {'Hamiltonian': {'DFTB': {'SCC': True}}}
        """
        string = super().__str__()
        string += "\n" + str(self.get_dict())
        return string
