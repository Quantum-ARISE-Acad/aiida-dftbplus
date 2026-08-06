# Query results with the QueryBuilder

The reason for storing the DFTB+ input as a dictionary rather than a file is
that it stays queryable. This page collects the queries you will actually use.

```python
from aiida import orm
from aiida.orm import QueryBuilder
from aiida.plugins import CalculationFactory, DataFactory

DftbPlusCalculation = CalculationFactory("dftbplus")
DftbParameters = DataFactory("dftbplus")
```

## All calculations and their energies

```python
query = QueryBuilder()
query.append(DftbPlusCalculation, tag="calc", project=["id", "label", "attributes.exit_status"])
query.append(orm.Dict, with_incoming="calc", edge_filters={"label": "output_parameters"},
             project=["attributes.total_energy_eV", "attributes.max_force_eV_Ang"])

for pk, label, exit_status, energy, force in query.iterall():
    print(f"{pk:<6} {label or '':<20} exit={exit_status} E={energy} Fmax={force}")
```

`edge_filters={"label": "output_parameters"}` is what distinguishes the parsed
results from any other `Dict` attached to the calculation — the `structure`
metadata is a `Dict` too.

## Filter on an input setting

Attributes nest with dots, exactly as the dictionary does:

```python
query = QueryBuilder()
query.append(DftbParameters, filters={
    "attributes.Hamiltonian.DFTB.SCC": True,
    "attributes.Hamiltonian.DFTB.MaxSCCIterations": {">": 100},
}, tag="params")
query.append(DftbPlusCalculation, with_incoming="params", project=["id"])
print(query.all(flat=True))
```

Useful operators: `>`, `<`, `>=`, `<=`, `==`, `!==`, `in`, `like` (with `%` as
the wildcard), `has_key`, `of_type`.

## Only the successful ones

```python
query = QueryBuilder()
query.append(DftbPlusCalculation, filters={"attributes.exit_status": 0}, project=["id"])
```

And only the failures, grouped by reason:

```python
from collections import Counter

query = QueryBuilder()
query.append(DftbPlusCalculation, filters={"attributes.exit_status": {"!==": 0}},
             project=["attributes.exit_status"])
print(Counter(status for (status,) in query.all()))
# Counter({320: 6, 310: 2})
```

## Find the lowest-energy structure

```python
query = QueryBuilder()
query.append(DftbPlusCalculation, tag="calc", project=["id"])
query.append(orm.Dict, with_incoming="calc", edge_filters={"label": "output_parameters"},
             project=["attributes.total_energy_eV"])
query.order_by({orm.Dict: {"attributes.total_energy_eV": "asc"}})
query.limit(5)
print(query.all())
```

## Everything in a campaign

```python
query = QueryBuilder()
query.append(orm.Group, filters={"label": "dftb/screening-2026-08"}, tag="group")
query.append(DftbPlusCalculation, with_group="group", tag="calc", project=["id", "label"])
query.append(orm.Dict, with_incoming="calc", edge_filters={"label": "output_parameters"},
             project=["attributes.total_energy_eV"])
```

## Trace a result back to its inputs

```python
node = orm.load_node(<PK>)

print(node.inputs.code.full_label)
print(node.inputs.parameters.get_dict()["Hamiltonian"]["DFTB"])
print(node.inputs.structure.get_dict())          # your metadata
print(node.base.links.get_incoming().all())      # every input link
print(node.base.links.get_outgoing().all())      # every output link
```

Or visually:

```shell
verdi node graph generate <PK>
```

## Which calculations used a given SKF folder

```python
query = QueryBuilder()
query.append(orm.FolderData, filters={"label": "skf_mio-1-1_H-O"}, tag="skf")
query.append(DftbPlusCalculation, with_incoming="skf", project=["id", "label"])
print(query.count(), "calculations used that parameter folder")
```

This is the reproducibility payoff of shipping `skf_files`: the parameters are a
node, so "what was computed with these exact files?" is one query.

## Export the lot

```python
import csv

query = QueryBuilder()
query.append(DftbPlusCalculation, tag="calc", project=["id", "label"])
query.append(orm.Dict, with_incoming="calc", edge_filters={"label": "output_parameters"},
             project=["attributes.total_energy_eV", "attributes.max_force_eV_Ang",
                      "attributes.scc_converged"])

with open("results.csv", "w", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["pk", "label", "energy_eV", "max_force_eV_Ang", "scc_converged"])
    writer.writerows(query.iterall())
```

`iterall()` streams instead of building the whole list in memory — the right
choice once a campaign has thousands of calculations.
