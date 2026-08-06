# A short primer on DFTB

Enough theory to use the plugin responsibly, and an honest account of where the
method breaks down. If you are choosing between DFTB and DFT for a project, read
the limitations section first.

## What DFTB is

Density-functional tight binding is DFT with almost everything precomputed. The
Kohn–Sham energy is expanded around a reference density and truncated:

- **DFTB1 / non-SCC** — zeroth order. The Hamiltonian and overlap matrix elements
  come from tables built once per element pair; the calculation is a single
  diagonalisation. No charge transfer.
- **DFTB2 / SCC** — second order. Adds a self-consistent charge cycle, so atoms
  can polarise each other. This is what `SCC = Yes` turns on, and it is the
  usual starting point.
- **DFTB3** — third order, with a per-element Hubbard derivative. Needed for
  hydrogen bonding and charged systems, and what the `3ob` set expects
  (`ThirdOrderFull`, `HCorrection`, `HubbardDerivs`).

The tables are the `.skf` files. That is where the physics that was not computed
at run time has gone: someone fitted it, once, for a class of systems.

## What it buys you

Two to three **orders of magnitude** faster than DFT for the same system, with
memory to match. That changes what is possible:

- thousands of structures screened where DFT would allow ten;
- molecular dynamics over nanoseconds rather than picoseconds;
- systems of thousands of atoms — nanotubes, proteins, large surfaces;
- an inexpensive pre-relaxation before a DFT refinement.

## What it costs you

The approximations are real, and pretending otherwise produces bad papers.

**The parameters are the method.** A DFTB calculation is only as good as the SKF
set, and a set is fitted for a purpose. Using an organic set on an oxide gives
you numbers with no meaning. The set is a physics choice you must state and
cite.

**Transferability is limited.** DFTB extrapolates poorly away from the systems
its parameters were fitted to. New chemistry means new parameters, and new
parameters are months of work.

**Minimal basis.** Usually one s and one p shell per element (plus d where the
set provides it). Anything requiring a rich basis — polarisability, excited
states, weak long-range interactions — is systematically off.

**No dispersion by default.** Van der Waals forces are absent unless you add a
correction (`Dispersion = LennardJones {}`, `Dispersion = DftD3 {}`, ...).
Layered materials and molecular crystals will not hold together without one.

**Band gaps and barriers.** Gaps inherit DFT's underestimation, then add the
parameterisation's own error. Reaction barriers are often off by tens of
kJ/mol.

**Elements.** Many elements have no published parameters at all, and coverage of
the transition metals and lanthanides is patchy.

For a sense of scale, the water relaxation in [T2](../tutorials/t2-relaxation.md)
gives an O–H bond ~3 % long and an angle ~3° narrow against experiment. That is
typical, and it is fine for screening and hopeless for spectroscopic accuracy.

## When to use DFTB

Good fits:

- screening many candidates before refining a few with DFT;
- large systems where DFT is simply out of reach;
- long-timescale dynamics where relative energies matter more than absolute ones;
- geometry pre-optimisation;
- teaching, where the turnaround time makes experimentation possible.

Bad fits:

- publication-quality energetics without validation against a higher method;
- systems outside the parameter set's intended chemistry;
- anything dominated by dispersion, without an explicit correction;
- excited states and optical properties, unless you know exactly what the set
  supports;
- elements with no parameters — no software can fix that.

## Practical consequences for this plugin

- Total energies are **not** comparable across parameter sets. Compare only
  within one set.
- Record the set with each calculation (`structure` metadata), or the numbers
  become uninterpretable later.
- Validate a handful of results against DFT or experiment before trusting a
  campaign of thousands.
- A clean exit status says the code ran, not that the physics is right.

## Where to read more

- [DFTB+ manual](https://dftbplus.org/documentation) — every keyword, with
  defaults.
- [DFTB+ recipes](https://dftbplus-recipes.readthedocs.io) — worked examples by
  calculation type.
- [dftb.org/parameters](https://dftb.org/parameters) — the sets, their scope and
  their papers.
- The DFTB+ citation printed at the top of every `dftb.out`, and the paper for
  the parameter set you used. Both are expected in a publication.
