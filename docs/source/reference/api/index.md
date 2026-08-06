# API reference

Generated from the NumPy-style docstrings in `src/aiida_dftbplus` by
`sphinx.ext.autosummary`. Nothing on this page is hand-written: to change what
appears here, change a docstring in the source.

```{eval-rst}
.. autosummary::
   :toctree: _generated
   :template: autosummary/module.rst
   :recursive:

   aiida_dftbplus
   aiida_dftbplus.calculations
   aiida_dftbplus.parsers
   aiida_dftbplus.data
   aiida_dftbplus.cli
   aiida_dftbplus.helpers
```

## The process specification

AiiDA can render a `CalcJob`'s specification directly from the class, so this
table cannot drift from the code:

```{eval-rst}
.. aiida-calcjob:: DftbPlusCalculation
    :module: aiida_dftbplus.calculations
```

For the same information with commentary on *why* each port exists, see
[the input/output contract](../../architecture/io-contract.md).
