# How to cite

A DFTB+ calculation run through this plugin rests on three pieces of work, and
all three expect to be cited: **DFTB+ itself**, the **parameter set** you used,
and **AiiDA**. The plugin is a fourth, minor one.

## DFTB+

The reference is printed at the top of every `dftb.out` you produce — always use
the one your build names. For recent versions:

> *Recent Developments in DFTB+, a Software Package for Efficient Atomistic
> Quantum Mechanical Simulations*, J. Phys. Chem. A **129**, 5373–5390 (2025).
> <https://doi.org/10.1021/acs.jpca.5c01146>

```shell
verdi calcjob outputcat <PK> dftb.out | head -25      # the citation your run asks for
```

## The parameter set

**This is the one people forget.** A DFTB result is meaningless without saying
which Slater–Koster set produced it, and each set has its own paper, listed on
its page at <https://dftb.org/parameters>. The licence you accepted when
downloading asks you to cite it.

State the set and its version in the methods section — `mio-1-1`, `3ob-3-1`,
`pbc-0-3` — and keep it with the calculation:

```python
inputs["structure"] = orm.Dict({"formula": "H2O", "skf_set": "3ob-3-1"})
```

## AiiDA

> Giovanni Pizzi, Andrea Cepellotti, Riccardo Sabatini, Nicola Marzari, and
> Boris Kozinsky, *AiiDA: automated interactive infrastructure and database for
> computational science*, Comp. Mat. Sci. **111**, 218–230 (2016).
> <https://doi.org/10.1016/j.commatsci.2015.09.013>

AiiDA asks that its more recent papers be cited as well; see
<https://www.aiida.net/pages/about.html> for the current list.

## This plugin

There is no paper. Cite the software:

```bibtex
@software{aiida_dftbplus,
  title        = {aiida-dftbplus: an AiiDA plugin for DFTB+ calculations},
  author       = {{Quantum ARISE}},
  year         = {2026},
  url          = {https://github.com/Quantum-ARISE-Acad/aiida-dftbplus},
  note         = {Version 0.1.0a0},
  license      = {MIT},
}
```

Update `note` to the version you actually used:

```python
import aiida_dftbplus
print(aiida_dftbplus.__version__)
```

## Reproducibility beyond citation

A citation says which software; an archive says which calculation. Export the
campaign and deposit it alongside the paper:

```shell
verdi archive create paper-data.aiida --groups dftb/screening-2026-08
```

The archive carries the inputs, the outputs, the files and the links between
them, and imports into any AiiDA profile — which is a stronger claim than a
table of numbers. If you used `skf_files` rather than `use_remote_skf_path`, the
parameter files themselves are in it too.
