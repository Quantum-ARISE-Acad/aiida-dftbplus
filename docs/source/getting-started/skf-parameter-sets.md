# Slater–Koster parameter sets

Everything on this page is about one question: **which `.skf` files does my
calculation need, where do I get them, and how do I point the plugin at them?**

Get this wrong and one of two things happens. Either DFTB+ stops with an error
naming a file it could not open — annoying, but honest. Or it runs to
completion with a set that was never parameterised for your problem and returns
numbers that look perfectly reasonable and are wrong. The second failure is the
expensive one, and no amount of software can catch it for you.

## What these files are

DFTB is a tight-binding method: instead of computing integrals on the fly, it
looks up **pre-tabulated** Hamiltonian and overlap matrix elements as a function
of interatomic distance. Those tables are the Slater–Koster files. They are
produced once, by hand, for a specific pair of elements and a specific
purpose — organic molecules, silicon bands, transition-metal oxides — by
choosing confining potentials and reference densities that reproduce known
results for that class of system.

Consequences you have to live with:

- A set covers **a fixed list of elements**. An element outside the list simply
  cannot be treated.
- Parameters are **per element pair**, and DFTB+ needs both orderings —
  `O-S.skf` *and* `S-O.skf`.
- Sets are **not interchangeable and must not be mixed**. Files from two sets
  were fitted against different references; combining them is not a supported
  operation, whatever the file names suggest.
- The set dictates other input settings — the angular momenta, and for a DFTB3
  set the Hubbard derivatives and the H-damping. Those are documented with the
  set, not guessable from the files.

## Where to get them

| Source | What is there |
| --- | --- |
| <https://dftb.org/parameters> | The official index of parameter sets, one page per set with its element list, intended use, and the paper to cite |
| <https://dftb.org/parameters/download> | The download area. Sets are free for academic use; you accept a licence per set, and some ask you to register first |
| <https://dftbplus-recipes.readthedocs.io> | The DFTB+ recipes: worked examples that show which set was used for which kind of calculation |
| Your group's shared storage | Most groups keep a copy on the cluster. Ask before downloading 1.5 GB again — and see [remote paths](#two-ways-to-supply-the-files) below |

Download, unpack, and keep the set's own `README` next to the files. That README
is where the angular momenta and the citation live.

```shell
mkdir -p ~/skf && cd ~/skf
# after accepting the licence on dftb.org, e.g.:
tar -xzf mio-1-1.tar.gz
ls mio-1-1/ | head
# C-C.skf  C-H.skf  C-N.skf  C-O.skf  C-S.skf  H-C.skf  H-H.skf ...
```

## Which set to use

The set is a physics decision, not a configuration detail. The table below is
a starting point for the most commonly used sets; **the authoritative
description of each is its page on dftb.org**, and that is what you should read
before using one in published work.

| Set | Typically used for | Notes |
| --- | --- | --- |
| `mio` | Organic and biological molecules — H, C, N, O, S, P | The original DFTB2 set; the safe default for a first test on an organic molecule |
| `3ob` | The same chemistry at DFTB3 level, plus many ions | Requires DFTB3 settings (see below). Generally the better choice for organics today |
| `matsci` | Materials science: solids, oxides, ceramics | Built for bulk and surfaces rather than isolated molecules |
| `pbc` | Periodic solids and semiconductors, e.g. silicon | Used by the band-structure examples |
| `halorg` | Halogens together with organic elements | Extends organic sets to Cl, Br, I |
| `znorg`, `tiorg`, `borg`, `trans3d` | Specific metals with organic ligands / 3d transition metals | Narrow scope by design |
| A full periodic-table set | Screening across many chemistries | Large — thousands of files. See the [performance warning](#ship-only-what-the-run-reads) |

:::{warning}
Element coverage is not the criterion. A set that lists your elements may still
be the wrong set — `mio` will happily run on a crystal it was never fitted for.
Match the set to the *kind of system and property* you are computing, and say in
your paper which set you used.
:::

## What a set makes you write in the input

### The file-name block

Almost every input uses `Type2FileNames`, which builds the file name from the
two element symbols:

```
Hamiltonian = DFTB {
  SlaterKosterFiles = Type2FileNames {
    Prefix = "/home/me/skf/mio-1-1/"
    Separator = "-"
    Suffix = ".skf"
  }
}
```

That produces `/home/me/skf/mio-1-1/C-H.skf` and so on. The trailing slash on
`Prefix` is required — it is string concatenation, not a path join.

You can also name every file explicitly, which is occasionally useful when the
names do not follow the convention:

```
SlaterKosterFiles {
  H-H = "H-H.skf"
  H-O = "H-O.skf"
  O-H = "O-H.skf"
  O-O = "O-O.skf"
}
```

### The angular momenta (mandatory)

`MaxAngularMomentum` must list **every element in your structure**, with the
shell the set was parameterised with. It is not optional and DFTB+ will not
guess:

```
Hamiltonian = DFTB {
  MaxAngularMomentum {
    H = "s"
    C = "p"
    N = "p"
    O = "p"
    S = "d"
  }
}
```

Take these values from the set's documentation. As a **cross-check only**, a
homonuclear file tells you what it carries: line 2 of `X-X.skf` holds
`Ed Ep Es SPE Ud Up Us fd fp fs`, so a zero `Ed` with a non-zero `Ep` means the
file has s and p shells, and a non-zero `Ed` means d is included.

```shell
sed -n '2p' ~/skf/mio-1-1/S-S.skf
```

Setting a lower momentum than the set provides silently changes the physics;
setting a higher one than it provides makes DFTB+ stop.

### Extra settings some sets require

DFTB3 sets such as `3ob` are not drop-in replacements for a DFTB2 set. They
require the third-order terms and the hydrogen-bonding correction to be turned
on, and the per-element Hubbard derivatives to be supplied:

```
Hamiltonian = DFTB {
  ThirdOrderFull = Yes
  HCorrection = Damping { Exponent = 4.0 }
  HubbardDerivs {
    H = -0.1857
    C = -0.1492
    N = -0.1535
    O = -0.1575
    S = -0.1100
  }
}
```

The exponent and the derivative values belong to the set — copy them from its
documentation rather than from here, and never mix values from different sets.
Spin-polarised calculations likewise need spin constants that come with the set.

In this plugin, blocks like these are most easily written as raw passthrough
text:

```python
parameters = {
    "Hamiltonian": {"DFTB": {
        "SCC": True,
        "ThirdOrderFull": True,
        "_raw_1": 'HCorrection = Damping { Exponent = 4.0 }',
        "_raw_2": 'HubbardDerivs {\n  H = -0.1857\n  O = -0.1575\n}',
    }},
}
```

## Two ways to supply the files

The plugin gives you a choice, and it is a real trade-off.

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} `use_remote_skf_path=True`
The files already sit on the machine that runs DFTB+. The absolute `Prefix` in
your input is left untouched and **nothing is uploaded**.

```python
inputs["use_remote_skf_path"] = orm.Bool(True)
```

**Use this for** a full parameter set, a shared cluster installation, or any
campaign where the same set is read by thousands of jobs.

**Cost:** the path is not recorded as data. If the directory changes, old
calculations are no longer reproducible from the database alone.
:::

:::{grid-item-card} `skf_files` (a `FolderData`)
The files travel with the job. The plugin rewrites the `Prefix` to `"./"` and
the engine copies the folder into the working directory.

```python
inputs["skf_files"] = folder   # orm.FolderData
```

**Use this for** reproducibility: the exact parameters are stored in the
database and linked to the calculation for ever.

**Cost:** copying. See the warning below.
:::

::::

### Ship only what the run reads

:::{danger}
Uploading a whole parameter set with every job is the single worst performance
mistake you can make with this plugin. A real measurement from this project:

| | Full set | Only the pairs needed |
| --- | --- | --- |
| Files per job | 5625 | 4 |
| Data per job | 1.5 GB | 904 kB |
| Six jobs, submit → finished | ~50 min | ~1 min |
| DFTB+ time per job | 0.79 s | 0.79 s |

The daemon workers spent all their time in disk wait while the science took
under a second. Build a folder with the pairs your structure actually needs.
:::

For a system containing only O and S, that is four files:

```python
from itertools import product
from pathlib import Path
from aiida import orm

skf_dir = Path.home() / "skf" / "mio-1-1"
elements = ["O", "S"]

skf_files = orm.FolderData()
for first, second in product(elements, repeat=2):
    name = f"{first}-{second}.skf"
    skf_files.put_object_from_file(str(skf_dir / name), name)
skf_files.label = f"mio-1-1_{'-'.join(elements)}"
skf_files.store()
```

Reuse that node across every calculation with the same elements — it is stored
once and linked many times:

```python
from aiida.orm import QueryBuilder

query = QueryBuilder().append(orm.FolderData, filters={"label": "mio-1-1_O-S"})
skf_files = query.first(flat=True) or build_it()
```

The [high-throughput tutorial](../tutorials/t5-high-throughput.md) turns this
into a reusable helper that reads the element list out of the input itself.

## Checklist before you submit

```{list-table}
:header-rows: 1
:widths: 45 55

* - Check
  - How
* - The set covers every element in the structure
  - Read the set's page on dftb.org
* - Both orderings of every pair exist
  - `ls skf_dir | wc -l` should be n² for n elements
* - `MaxAngularMomentum` lists every element
  - Compare with the set's README
* - DFTB3 settings present, if the set is a DFTB3 set
  - `ThirdOrderFull`, `HCorrection`, `HubbardDerivs`
* - The `Prefix` path exists on the machine that will read it
  - `ls "$PREFIX"` on that machine, not on your laptop
* - You are shipping only the pairs you need, or using the remote path
  - Count the files in your `FolderData`
```

## When it goes wrong

`ERROR!` naming a file it could not open
: A missing pair, or a `Prefix` without its trailing slash. Check both orderings
  exist.

Non-existent path that "works anyway"
: With `skf_files` supplied, the plugin rewrites the prefix to `"./"` before
  writing `dftb_in.hsd` — so a stale absolute path in your input is masked and
  keeps working. The same input with `use_remote_skf_path=True` will fail. If
  you switch modes and it suddenly breaks, this is why.

Results that look plausible but are wrong
: Wrong set for the chemistry, mixed sets, or a `MaxAngularMomentum` that does
  not match the set. None of these produces an error message. Re-read the set's
  documentation.

More diagnostics in [Handle common errors](../how-to/errors.md).

## Citing

Each set has its own paper, listed on its dftb.org page, and the licence asks
you to cite it. Record which set you used — the `structure` input port is a
convenient place to keep that metadata with the provenance:

```python
inputs["structure"] = orm.Dict({"formula": "H2O", "skf_set": "3ob-3-1"})
```

Next: [Your first calculation](first-calculation.md).
