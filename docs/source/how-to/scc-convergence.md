# Control SCC convergence and diagnose non-convergence

## What exit code 320 means

DFTB+ ran, the SCC cycle hit `MaxSCCIterations` without reaching
`SCCTolerance`, and the plugin classified it as **320 —
`ERROR_SCC_NOT_CONVERGED`**. The calculation is not broken: the outputs are
retrieved and readable. Only `output_parameters` is missing, because attaching
unconverged numbers would invite using them.

The parser logs this as a *warning*, not an error, for the same reason.

## The knobs, in the order to try them

```python
dftb = parameters["Hamiltonian"]["DFTB"]
```

**1. More iterations.** The cheapest thing to try, and often enough:

```python
dftb["MaxSCCIterations"] = 500        # default in most examples is 100
```

**2. A gentler mixer.** Charge sloshing between iterations is the usual cause;
a smaller mixing parameter damps it:

```python
dftb["_raw_mixer"] = "Mixer = Broyden {\n  MixingParameter = 0.05\n}"
```

Broyden with 0.2 is the DFTB+ default. Going below ~0.01 usually means the
problem is elsewhere.

**3. Electronic temperature.** A small or vanishing gap makes occupations jump
between iterations. Smearing them stabilises the cycle:

```python
dftb["_raw_filling"] = "Filling = Fermi {\n  Temperature [K] = 1000\n}"
```

Remember this changes the physics: the energy you get is a free energy at that
temperature. Converge with smearing, then re-run at a lower temperature from the
converged charges.

**4. Start from better charges.** Restart from a converged `charges.bin` of a
related calculation — a looser tolerance, a smaller k-mesh, a slightly different
geometry. See [Restart](restart.md).

**5. Loosen the tolerance.** Last, and only deliberately:

```python
dftb["SCCTolerance"] = 1e-4           # from 1e-5
```

## Diagnose it, do not just retry

Read the SCC table in `dftb.out`:

```shell
verdi calcjob outputcat <PK> dftb.out | grep -A 40 "iSCC"
```

```text
 iSCC Total electronic   Diff electronic      SCC error
    1   -0.73237750E+00    0.00000000E+00    0.00000000E+00
    2   -0.73240010E+00   -0.22600000E-04    0.31000000E-03
```

What the trace tells you:

| Pattern in `SCC error` | Likely cause | Fix |
| --- | --- | --- |
| Falls steadily, just runs out of steps | Tolerance is reachable, budget too small | More iterations |
| Oscillates between two values | Charge sloshing | Smaller mixing parameter |
| Falls then rises again | Degenerate states near the Fermi level | Fermi filling with a temperature |
| Never moves from the first value | Something is wrong with the input, not the cycle | Read `dftb_pin.hsd` |
| Diverges immediately | Bad geometry (overlapping atoms), or wrong parameters for these elements | Check the structure and the SKF set |

`dftb_pin.hsd` — DFTB+'s processed input with every default written out — is the
fastest way to see that a setting you thought you set is not there.

## When the geometry is the problem

Atoms much closer than a bond length make the SCC cycle diverge on the first
step. Before blaming the solver, check the shortest distance in your structure:

```python
import itertools, math

coords = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.75)]
print(min(math.dist(a, b) for a, b in itertools.combinations(coords, 2)))
```

Anything under ~0.5 Å is unphysical for most elements.

## Prevention

For a campaign, converge one representative system by hand first, then reuse
those settings. The alternative — submitting a thousand jobs with default
settings and triaging the failures — costs far more queue time.

Automating the retry is [T6](../tutorials/t6-custom-workchain.md).
