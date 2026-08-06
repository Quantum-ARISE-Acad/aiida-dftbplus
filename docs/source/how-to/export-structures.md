# Export structures and results

The plugin produces no {class}`~aiida.orm.nodes.data.structure.StructureData`
and no CIF. Geometry comes back as `geom.out.gen` and `geom.out.xyz` inside the
`retrieved` folder, and converting is up to you. Everything below is a few lines
because the formats are simple.

## Get the files out

```python
from aiida import orm

node = orm.load_node(<PK>)

with node.outputs.retrieved.open("geom.out.xyz") as handle:
    xyz_text = handle.read()

with open("relaxed.xyz", "w") as handle:
    handle.write(xyz_text)
```

or from the shell:

```shell
verdi calcjob outputcat <PK> geom.out.xyz > relaxed.xyz
verdi calcjob outputcat <PK> geom.out.gen > relaxed.gen
```

:::{note}
The XYZ that DFTB+ writes carries a **fifth column** with the Mulliken charge on
each atom. Most readers ignore it; a strict one may not. Strip it if needed.
:::

## To ASE

```python
import io

from ase.io import read

with node.outputs.retrieved.open("geom.out.gen") as handle:
    atoms = read(io.StringIO(handle.read()), format="gen")

print(atoms.get_chemical_formula(), atoms.get_cell())
atoms.write("relaxed.cif")
```

ASE reads and writes the GEN format natively, which makes it the shortest route
to CIF, POSCAR, or anything else. ASE is **not** a dependency of this plugin —
`pip install ase`. Its documentation is at <https://ase-lib.org>.

## To pymatgen

pymatgen has no GEN reader, so go through ASE, or through a CIF that ASE wrote:

```python
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor

structure = AseAtomsAdaptor.get_structure(atoms)     # periodic systems
print(structure.composition, structure.lattice)
structure.to(filename="relaxed.cif")
```

For a molecule, use {class}`~pymatgen.core.structure.Molecule` and
`AseAtomsAdaptor.get_molecule(atoms)` instead.

## To an AiiDA StructureData

If you want the relaxed geometry as a node — so downstream calculations link to
it — build it inside a `calcfunction`, so the provenance records where it came
from:

```python
import io

from aiida import orm
from aiida.engine import calcfunction
from ase.io import read


@calcfunction
def structure_from_retrieved(retrieved):
    """Read geom.out.gen from a retrieved folder into a StructureData."""
    with retrieved.open("geom.out.gen") as handle:
        atoms = read(io.StringIO(handle.read()), format="gen")
    return orm.StructureData(ase=atoms)


structure = structure_from_retrieved(node.outputs.retrieved)
```

Without the decorator you get an orphan node that no query can connect to the
calculation that produced it.

## Read the GEN format yourself

No dependency needed — the format is four kinds of line:

```python
def read_gen(text):
    """Return (species, [(symbol, x, y, z)], lattice or None)."""
    lines = [line for line in text.splitlines() if line.strip()]
    count, kind = lines[0].split()[:2]
    count, kind = int(count), kind.upper()
    species = lines[1].split()

    atoms = []
    for line in lines[2 : 2 + count]:
        _, species_index, x, y, z = line.split()[:5]
        atoms.append((species[int(species_index) - 1], float(x), float(y), float(z)))

    lattice = None
    if kind in ("S", "F"):
        rows = lines[2 + count : 2 + count + 4]        # origin + 3 vectors
        lattice = [[float(value) for value in row.split()] for row in rows[1:]]

    return species, atoms, lattice
```

`C` is a cluster (no lattice), `S` supercell with Cartesian coordinates, `F`
supercell with fractional coordinates.

## Export the parsed numbers

```python
results = node.outputs.output_parameters.get_dict()
print(results["total_energy_eV"], results["max_force_eV_Ang"])
```

For a whole campaign in one CSV, see [Query results](query-results.md).

## Export the provenance itself

```shell
verdi archive create results.aiida --groups dftb/screening-2026-08
verdi node graph generate <PK> --output-format pdf
```

The archive holds nodes, files and links, and imports into any other AiiDA
profile. It is the right thing to attach to a paper: it contains the inputs, not
just the numbers.
