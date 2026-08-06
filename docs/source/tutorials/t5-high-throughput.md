# T5 — A high-throughput campaign

**Goal.** Submit many structures at once without drowning the daemon, then
collect the results with one query.

**Prerequisites.** [T4](t4-submit-monitor.md) — a working daemon.

This tutorial is built from a real failure. A batch of six materials was
submitted and was still unfinished 45 minutes later, with `verdi daemon status`
timing out. Nothing was broken: both workers were stuck copying **5625 SKF
files (1.5 GB) per job** for calculations that took 0.79 s of CPU each. The fix
below turned ~50 minutes into ~1 minute.

## Step 1 — group the run

Give every calculation in a campaign a group, so you can find them later without
remembering PKs:

```python
from aiida import orm

group, _ = orm.Group.collection.get_or_create(label="dftb/screening-2026-08")
```

## Step 2 — ship only the SKF files each structure needs

The one rule of high throughput with this plugin: **never upload a full
parameter set per job**. Build one `FolderData` per distinct element set, reuse
it across every structure with those elements, and cache it in the database so
repeated runs of the script do not rebuild it.

```python
import re
from itertools import product
from pathlib import Path

from aiida import orm

SKF_DIR = Path.home() / "skf" / "mio-1-1"
_CACHE = {}


def elements_in_hsd(hsd_text):
    """Return the element symbols listed in the MaxAngularMomentum block.

    That block is mandatory for a DFTB Hamiltonian and names exactly the
    species that need parameters, so it is the most reliable place to look.
    """
    match = re.search(r"MaxAngularMomentum\s*\{", hsd_text)
    if match is None:
        raise ValueError("no MaxAngularMomentum block: cannot tell which SKF files are needed")

    depth, index = 1, match.end()
    while depth and index < len(hsd_text):
        depth += {"{": 1, "}": -1}.get(hsd_text[index], 0)
        index += 1
    block = hsd_text[match.end() : index - 1]

    return sorted({line.split("=")[0].strip() for line in block.splitlines() if "=" in line})


def skf_folder_for(elements):
    """Return a stored FolderData with exactly the pairs these elements need."""
    label = f"skf_{SKF_DIR.name}_{'-'.join(elements)}"

    if label in _CACHE:
        return _CACHE[label]

    query = orm.QueryBuilder().append(orm.FolderData, filters={"label": label})
    existing = query.first(flat=True)
    if existing is not None:
        _CACHE[label] = existing
        return existing

    folder = orm.FolderData()
    for first, second in product(elements, repeat=2):
        name = f"{first}-{second}.skf"
        source = SKF_DIR / name
        if not source.exists():
            raise FileNotFoundError(f"{source} is missing: this set does not cover {first}-{second}")
        folder.put_object_from_file(str(source), name)

    folder.label = label
    folder.store()
    _CACHE[label] = folder
    return folder
```

Two things this buys you:

- **Missing parameters fail before submission**, with the name of the pair, not
  40 minutes later inside DFTB+.
- **The node is stored once and linked many times.** Fifty calculations on
  O/S materials share one `FolderData`; the database holds one copy.

## Step 3 — submit the batch

```python
from aiida import engine, orm
from aiida.plugins import CalculationFactory, DataFactory

DftbParameters = DataFactory("dftbplus")
DftbPlusCalculation = CalculationFactory("dftbplus")
code = orm.load_code("dftb+@localhost")

submitted, skipped = [], []

for name, parameter_dict in structures.items():          # your own dict of inputs
    parameters = DftbParameters(parameter_dict)

    try:
        elements = elements_in_hsd(parameters.get_hsd())
        skf_files = skf_folder_for(elements)
    except (ValueError, FileNotFoundError) as exc:
        skipped.append((name, str(exc)))
        continue

    builder = DftbPlusCalculation.get_builder()
    builder.code = code
    builder.parameters = parameters
    builder.skf_files = skf_files
    builder.structure = orm.Dict({"formula": name, "elements": elements})
    builder.metadata.label = name
    builder.metadata.options.max_wallclock_seconds = 1800
    builder.metadata.options.withmpi = False

    node = engine.submit(builder)
    group.add_nodes(node)
    submitted.append((name, node.pk))

print(f"submitted {len(submitted)}, skipped {len(skipped)}")
for name, reason in skipped:
    print(f"  skipped {name}: {reason}")
```

Points that matter at scale:

- **One bad structure must not take the batch down.** Collect the reason, skip
  it, report it at the end.
- **No `time.sleep` between submissions.** `engine.submit` returns as soon as
  the node is stored; the daemon paces itself.
- **`skf_files`, not `use_remote_skf_path`.** With the minimal folders, shipping
  the files costs kilobytes and buys full reproducibility. Use the remote path
  instead only when the set is large and shared.

## Step 4 — watch the batch

```shell
verdi process list -a -p 1
verdi group show dftb/screening-2026-08
watch -n 10 'verdi process list | tail -20'
```

Count the outcomes without reading the list by eye:

```python
from collections import Counter

states = Counter(node.exit_status for node in group.nodes if node.is_terminated)
print(states)      # Counter({0: 5, 320: 1})
```

## Step 5 — collect the results

One query walks the whole campaign — parameters, calculation and results
together:

```python
from aiida.orm import QueryBuilder
from aiida.plugins import CalculationFactory, DataFactory

query = QueryBuilder()
query.append(orm.Group, filters={"label": "dftb/screening-2026-08"}, tag="group")
query.append(CalculationFactory("dftbplus"), with_group="group", tag="calc",
             project=["id", "attributes.exit_status", "label"])
query.append(orm.Dict, with_incoming="calc", edge_filters={"label": "output_parameters"},
             project=["attributes.total_energy_eV", "attributes.max_force_eV_Ang"])

for pk, exit_status, label, energy, force in query.all():
    print(f"{label:<16} pk={pk:<6} exit={exit_status:<4} E={energy:12.4f} eV  Fmax={force:.4f} eV/A")
```

```text
SO2_SG2_1        pk=1998   exit=0     E=  -1043.2841 eV  Fmax=0.0217 eV/A
SO2_SG2_2        pk=2003   exit=0     E=  -1043.2839 eV  Fmax=0.0193 eV/A
...
```

Calculations that failed have no `output_parameters` and therefore do not appear
in that query at all — an inner join. To list them, query the calculations alone
and filter on `exit_status`:

```python
query = QueryBuilder()
query.append(orm.Group, filters={"label": "dftb/screening-2026-08"}, tag="group")
query.append(CalculationFactory("dftbplus"), with_group="group",
             filters={"attributes.exit_status": {"!==": 0}},
             project=["id", "label", "attributes.exit_status"])
print(query.all())
```

More patterns in [Query results](../how-to/query-results.md).

## Step 6 — what the provenance graph gives you

Every calculation in the group is linked to the exact parameter node, the exact
SKF folder and the exact code that produced it. Six months later, the question
"which parameter set did these energies come from?" is a query, not an
archaeology project:

```shell
verdi node graph generate <PK>          # one calculation, as a PDF
verdi archive create campaign.aiida --groups dftb/screening-2026-08
```

The archive is self-contained: inputs, outputs, files and links. It can be
imported into another profile, or attached to a paper.

## What you learned

- Building a minimal SKF `FolderData` per element set is the difference between
  a one-minute batch and a one-hour one.
- Validate what you can *before* submitting, and skip rather than abort.
- Groups turn a campaign into a queryable unit.
- The `QueryBuilder` joins parameters, calculations and results in one pass;
  failed calculations drop out of a results join and need their own query.

Next: [T6 — writing a WorkChain](t6-custom-workchain.md).
