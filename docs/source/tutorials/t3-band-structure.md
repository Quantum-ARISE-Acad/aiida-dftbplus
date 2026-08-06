# T3 — Band structure

**Goal.** Compute the silicon band structure along a k-path, in the two steps
DFTB+ requires, restarting the second from the charges of the first.

**Prerequisites.** [T1](t1-single-point.md) — you will reuse its `charges.bin`.

:::{important}
**The plugin does not parse `band.out`.** It retrieves the file and stops there:
there is no `BandsData` output, no k-path metadata, no plot. This tutorial shows
how to run the calculation and read the file yourself. If you want a
`BandsData`, [adding a second parser](../architecture/contributing.md#adding-to-the-parser)
is the honest route.
:::

## Why two calculations

A band structure needs eigenvalues on a *path* through the Brillouin zone, but
the self-consistent charges must come from a *mesh* that samples the whole zone.
So:

1. **SCC run on a mesh** — T1, which already produced converged `charges.bin`.
2. **Non-SCC run along a path** — read those charges, diagonalise once at each
   k-point of the path, write `band.out`.

Step 2 must not re-converge anything, which is why it sets
`MaxSCCIterations = 1` and `ReadInitialCharges = Yes`.

## Step 1 — carry the charges over

`charges.bin` is a file on the first calculation's `retrieved` node. Copy it
into a `FolderData` and pass it as `mat_files`, which the plugin stages into the
working directory:

```python
import io

from aiida import orm

first = orm.load_node(<PK of T1>)

charges = orm.FolderData()
with first.outputs.retrieved.open("charges.bin", "rb") as handle:
    charges.put_object_from_filelike(io.BytesIO(handle.read()), "charges.bin")
charges.store()
```

`mat_files` is the general "any other file this run needs" port. Anything in it
lands next to `dftb_in.hsd`, except a `dftb_in.hsd` of its own, which is skipped
so the generated input always wins.

## Step 2 — the k-path

```python
parameters = DataFactory("dftbplus")({
    "Geometry": {"GenFormat": {"_raw": GEOMETRY}},      # same cell as T1
    "Hamiltonian": {"DFTB": {
        "SCC": True,
        "MaxSCCIterations": 1,
        "ReadInitialCharges": True,
        "_raw_1": (
            'SlaterKosterFiles = Type2FileNames {\n'
            f'  Prefix = "{SKF_DIR}"\n'
            '  Separator = "-"\n  Suffix = ".skf"\n}'
        ),
        "_raw_2": 'MaxAngularMomentum {\n  Si = "d"\n}',
        "_raw_3": (
            "KPointsAndWeights = Klines {\n"
            "   1   0.5  0.5  0.5\n"     # L
            "  20   0.0  0.0  0.0\n"     # -> Gamma
            "  20   0.5  0.0  0.5\n"     # -> X
            "  10   0.625 0.25 0.625\n"  # -> U/K
            "  20   0.0  0.0  0.0\n}"    # -> Gamma
        ),
    }},
    "Options": {"WriteDetailedOut": True},
    "ParserOptions": {"ParserVersion": 12},
})

results, node = engine.run_get_node(
    CalculationFactory("dftbplus"),
    code=orm.load_code("dftb+@localhost"),
    parameters=parameters,
    mat_files=charges,
    use_remote_skf_path=orm.Bool(True),
    metadata={"options": {"max_wallclock_seconds": 900, "withmpi": False}},
)
```

In a `Klines` block each line is *number of steps* followed by the fractional
coordinates of the point to move to. The first line with `1` sets the starting
point; the path above is L → Γ → X → U/K → Γ, the standard route for a
face-centred cubic lattice.

## Step 3 — what comes back

```text
exit status: 0
  total_energy_H: -2.3966263402
  total_energy_eV: -65.215525030491
  fermi_energy_eV: -3.2911298750463
  scc_converged: True
```

:::{warning}
`scc_converged: True` here means only that `detailed.out` does not contain the
string `SCC is NOT converged`. With `MaxSCCIterations = 1` nothing was converged
at all — the charges were read in, used once, and that is the intended
behaviour. The total energy of a band-structure run is likewise not comparable
with the SCC energy from step 1: −65.2 eV against −69.4 eV. **Use step 1 for
energies and step 2 for eigenvalues only.**
:::

## Step 4 — read `band.out`

```python
with node.outputs.retrieved.open("band.out") as handle:
    text = handle.read()
print("\n".join(text.splitlines()[:6]))
```

```text
 KPT            1  SPIN            1  KWEIGHT    1.4084507042253521E-002
     1    -13.0888  2.00000
     2    -10.1694  2.00000
     3     -5.2830  2.00000
     4     -5.2830  2.00000
     5     -3.1664  0.00000
```

The format is one block per k-point: a `KPT` header, then one line per band with
*band index, eigenvalue in eV, occupation*. Occupations of 2.0 are filled bands,
0.0 empty. Here bands 1–4 are the valence bands of the two-atom cell and band 5
upward are conduction bands.

Parsing it into arrays needs no library:

```python
def read_band_out(text):
    """Return a list of k-points, each a list of (energy_eV, occupation)."""
    kpoints, current = [], None
    for line in text.splitlines():
        if line.strip().startswith("KPT"):
            current = []
            kpoints.append(current)
        elif current is not None and line.strip():
            _, energy, occupation = line.split()
            current.append((float(energy), float(occupation)))
    return kpoints

kpoints = read_band_out(text)
print(len(kpoints), "k-points,", len(kpoints[0]), "bands each")

homo = max(e for e, occ in kpoints[0] if occ > 0.5)
lumo = min(e for e, occ in kpoints[0] if occ <= 0.5)
print(f"gap at the first k-point: {lumo - homo:.2f} eV")
```

To plot, transpose into one series per band and use matplotlib; the x-axis is
simply the k-point index unless you compute path distances yourself. The
`dp_bands` tool from `dftbplus-tools` does the same job from the command line:

```shell
verdi calcjob outputcat <PK> band.out > band.out
dp_bands band.out band          # writes band_tot.dat, ready to plot
```

## Step 5 — keep the two calculations linked

The two runs are separate nodes; what ties them together is the `charges`
`FolderData` you built in step 1. Because it is an input node of the second
calculation and was created from the first one's output, the provenance graph
already records the chain. Query it later with:

```shell
verdi node graph generate <PK of T3>
```

## What you learned

- A band structure is two DFTB+ runs: SCC on a mesh, then non-SCC on a path.
- `mat_files` is how any extra input file — here `charges.bin` — reaches the
  working directory.
- `band.out` is retrieved but not parsed; its format is simple enough to read in
  a dozen lines of Python.
- `scc_converged` and the total energy of a non-SCC run are not meaningful.

Next: [T4 — submitting and monitoring](t4-submit-monitor.md).
