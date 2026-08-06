# Command line interface

The plugin adds one command group to `verdi`, through the `aiida.cmdline.data`
entry point. All three commands are read-only.

```shell
verdi data dftbplus --help
```

## `verdi data dftbplus list`

Every `DftbParameters` node in the profile, one per line, with its PK.

```shell
verdi data dftbplus list
```

```text
uuid: 3f1c... (pk: 1873)
{'Geometry': {...}, 'Hamiltonian': {'DFTB': {'SCC': True, ...}}}, pk: 1873
```

Nodes stored as a plain `Dict` rather than as `DftbParameters` do not appear —
the query is on the node type. For a filtered or projected listing, use the
[QueryBuilder](../how-to/query-results.md).

## `verdi data dftbplus export`

The node as plain text: its identifier line followed by the dictionary.

```shell
verdi data dftbplus export 1873
verdi data dftbplus export 1873 --outfile parameters.txt
```

The identifier may be a PK, a UUID, or a label.

## `verdi data dftbplus hsd`

The node rendered as the `dftb_in.hsd` it would produce. The useful one:

```shell
verdi data dftbplus hsd 1873
verdi data dftbplus hsd 1873 -o dftb_in.hsd
```

```text
Geometry = GenFormat {
  2  C
    H
       1 1    0.0000000000E+00   0.0000000000E+00   0.0000000000E+00
       2 1    0.0000000000E+00   0.0000000000E+00   0.7500000000E+00
}
Hamiltonian = DFTB {
  SCC = Yes
  MaxSCCIterations = 100
  ...
```

This is the text **before** the two optional patches (SKF prefix, output
prefix). Passing a node that is not a `DftbParameters` fails with a clear
message rather than a traceback:

```text
Error: Node <1874> is a Dict, not a DftbParameters node.
```

## Related verdi commands

Not part of this plugin, but the ones you will use with it:

```{list-table}
:header-rows: 1
:widths: 46 54

* - Command
  - Shows
* - `verdi plugin list aiida.calculations dftbplus`
  - The full input specification, from the code
* - `verdi process list -a -p 1`
  - Everything from the last day
* - `verdi process show <PK>`
  - Inputs, outputs and links of one calculation
* - `verdi process report <PK>`
  - Log messages, including parser warnings
* - `verdi calcjob res <PK>`
  - The parsed scalars, as JSON
* - `verdi calcjob inputls / inputcat <PK>`
  - What the plugin wrote — `dftb_in.hsd`
* - `verdi calcjob outputls / outputcat <PK>`
  - What came back — `detailed.out`, `dftb.out`, ...
* - `verdi calcjob gotocomputer <PK>`
  - Drops you into the remote working directory
* - `verdi node graph generate <PK>`
  - The provenance graph as a PDF
* - `verdi archive create out.aiida --groups <label>`
  - A self-contained export of a campaign
```
