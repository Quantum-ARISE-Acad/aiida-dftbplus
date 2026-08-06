# Acknowledgements

## The software this plugin depends on

**[DFTB+](https://dftbplus.org)** — the DFTB+ developers group. This plugin is a
wrapper; every physical result you obtain through it is DFTB+'s work.

**[AiiDA](https://www.aiida.net)** — the AiiDA team at EPFL and the AiiDA
community. The engine, the provenance model, the scheduler and transport layers
and the `verdi` command line all come from aiida-core; this package adds two
classes to them.

**The Slater–Koster parameter developers** — the groups that produce and
maintain the sets published at <https://dftb.org/parameters>. Parameterisation
is months of careful work per set, and it is what makes DFTB usable at all.

**[voluptuous](https://github.com/alecthomas/voluptuous)** — the schema
validation behind `DftbParameters`.

## Project history

The package was generated from the
[AiiDA plugin cutter](https://github.com/aiidateam/aiida-plugin-cutter)
template, and grew from the needs of a real screening campaign — which is also
where its central performance decision was found, at the cost of a stalled batch
and 25 GB of unnecessary file copying.

## Maintainers

Developed at **Quantum ARISE**: AMUZUGA Wisdom and LABBAH Elie.

Contact: <sitouamu510@gmail.com>
Repository: <https://github.com/Quantum-ARISE-Acad/aiida-dftbplus>

## Funding

No funding source is recorded for this work. If you add one, this page is where
it belongs, together with any grant numbers your funder requires you to publish.

## Contributing

Bug reports, parameter-set experience and pull requests are all welcome — see
[Contributing](architecture/contributing.md).
