"""AiiDA plugin for DFTB+ calculations.

The package registers four AiiDA entry points, all named ``dftbplus``:

===========================  ==========================================================
Entry point group            Object
===========================  ==========================================================
``aiida.calculations``       :class:`~aiida_dftbplus.calculations.DftbPlusCalculation`
``aiida.parsers``            :class:`~aiida_dftbplus.parsers.DftbPlusParser`
``aiida.data``               :class:`~aiida_dftbplus.data.DftbParameters`
``aiida.cmdline.data``       ``aiida_dftbplus.cli.data_cli`` (``verdi data dftbplus``)
===========================  ==========================================================

Load them the AiiDA way rather than by importing the modules directly, so the
plugin registry stays the single source of truth::

    from aiida.plugins import CalculationFactory, DataFactory

    DftbPlusCalculation = CalculationFactory('dftbplus')
    DftbParameters = DataFactory('dftbplus')
"""

__version__ = "0.1.0a0"
