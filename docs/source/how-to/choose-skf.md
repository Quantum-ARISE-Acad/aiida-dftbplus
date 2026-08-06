# Choose and configure SKF sets

The full discussion — what these files are, where to download them, and how to
pick a set — is in
[Slater–Koster parameter sets](../getting-started/skf-parameter-sets.md). This
page is the operational summary.

## Decide how to supply them

```{list-table}
:header-rows: 1
:widths: 30 35 35

* - Situation
  - Use
  - Why
* - Full parameter set, shared cluster installation
  - `use_remote_skf_path=True`
  - Uploading thousands of files per job is what makes a batch take an hour
* - A handful of element pairs
  - `skf_files` (a `FolderData`)
  - Kilobytes, and the exact parameters are stored with the calculation
* - Reproducibility matters more than speed
  - `skf_files`
  - The database holds the files; a moved directory cannot invalidate old work
* - You are not sure
  - `skf_files` with only the pairs you need
  - Cheap and reproducible
```

## Ship only the pairs you need

```python
from itertools import product
from pathlib import Path

from aiida import orm

def skf_folder(skf_dir, elements, label=None):
    """FolderData with the n^2 files needed for these elements."""
    skf_dir = Path(skf_dir)
    folder = orm.FolderData()
    for first, second in product(elements, repeat=2):
        name = f"{first}-{second}.skf"
        source = skf_dir / name
        if not source.exists():
            raise FileNotFoundError(f"{source} is missing")
        folder.put_object_from_file(str(source), name)
    folder.label = label or f"skf_{skf_dir.name}_{'-'.join(sorted(elements))}"
    return folder.store()

inputs["skf_files"] = skf_folder("~/skf/mio-1-1", ["O", "H"])
```

With `skf_files` supplied, the plugin rewrites the `Prefix` in your input to
`"./"`, because the files land next to `dftb_in.hsd` in the working directory.
You do not have to change the input yourself.

## Reuse the node

Build it once, find it thereafter:

```python
query = orm.QueryBuilder().append(orm.FolderData, filters={"label": "skf_mio-1-1_H-O"})
existing = query.first(flat=True)
folder = existing if existing is not None else skf_folder("~/skf/mio-1-1", ["O", "H"])
```

## Keep the absolute path instead

```python
inputs["use_remote_skf_path"] = orm.Bool(True)
```

Now nothing is uploaded and the `Prefix` in your input is used as written — so
it must be correct **on the machine that runs DFTB+**, not on your laptop. This
is the mode where a stale path fails loudly, which is a feature: with
`skf_files` the rewrite to `"./"` hides a wrong path completely.

## Record which set you used

The `structure` port is metadata only, kept for provenance — a good place for it:

```python
inputs["structure"] = orm.Dict({
    "formula": "H2O",
    "skf_set": "3ob-3-1",
    "skf_source": "https://dftb.org/parameters",
})
```

Then the question "which parameters produced these energies?" is a query:

```python
query = orm.QueryBuilder()
query.append(orm.Dict, filters={"attributes.skf_set": "3ob-3-1"}, tag="meta")
query.append(CalculationFactory("dftbplus"), with_incoming="meta")
print(query.count())
```
