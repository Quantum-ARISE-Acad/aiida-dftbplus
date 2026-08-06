# How the plugin works

From a Python dictionary to a parsed result, with nothing skipped.

```{graphviz} ../_static/diagrams/lifecycle.dot
:caption: The path of one calculation. The plugin owns exactly the two blue boxes.
:align: center
```

## 1. You build inputs

You assemble AiiDA nodes: a `Code`, a `Dict` (or `DftbParameters`) of settings,
optionally `FolderData` nodes of files, and two `Bool` switches. Nothing has
happened yet — these are just nodes.

When you call `engine.submit`, the engine stores every input node, creates a
`CalcJobNode`, and links them. **From this moment the inputs are immutable.**
That is what makes the record trustworthy: nothing can be edited after the fact
to make the result look different.

## 2. The engine calls `prepare_for_submission`

This is the plugin's first of two jobs. The engine hands it an empty *sandbox*
folder and expects a `CalcInfo` describing what to run.

Inside, in order:

1. **Obtain the HSD text.** From `parameters`, via `_dict_to_hsd`; or read from
   `dftb_input` verbatim. The validator has already guaranteed exactly one of
   the two exists.
2. **Patch it.** `_fix_output_prefix` turns `OutputPrefix = "./"` into
   `OutputPrefix = "geom.out"`, so the relaxed geometry is written to a file
   that can be retrieved. `_patch_skf_paths` rewrites the Slater–Koster prefix
   to `"./"`, but only when the files are being uploaded.
3. **Write `dftb_in.hsd`** into the sandbox.
4. **Queue the SKF folder** on `calcinfo.local_copy_list` as
   `(uuid, ".", ".")` — the whole node, flat into the working directory.
5. **Copy the material files** into the sandbox, skipping any `dftb_in.hsd`
   among them so the generated input wins.
6. **Build `CodeInfo` and `CalcInfo`**: stdout to `dftb.out`, stderr to
   `dftb.err`, and the list of eight files to retrieve.

All patching happens on a local string. No input node is modified — they are
immutable anyway, and the tests assert it.

## 3. The engine uploads and submits

The plugin is finished; it has no idea what happens next. The engine:

- copies the sandbox contents to the working directory on the computer;
- copies the `local_copy_list` nodes straight there, bypassing the sandbox;
- writes a submission script from the code's `prepend_text`, the resource
  options and the `CodeInfo`;
- hands that script to the scheduler through the transport;
- polls until the job leaves the queue.

The sandbox is also archived into the calculation node's own repository — which
is precisely why the SKF files must not go through it. See
[Design decisions](../architecture/design-decisions.md#skf-files-bypass-the-sandbox).

## 4. DFTB+ runs

```shell
dftb+ > dftb.out 2> dftb.err
```

No arguments: DFTB+ always reads `dftb_in.hsd` from the working directory. That
is why the plugin's entire input job is "write one file in the right place".

## 5. The engine retrieves

Eight names are requested:

`dftb.out`, `dftb.err`, `detailed.out`, `band.out`, `geom.out.gen`,
`geom.out.xyz`, `charges.bin`, `dftb_pin.hsd`

Files that do not exist are simply absent — a static calculation produces no
`geom.out.*` and that is not an error. AiiDA adds `_scheduler-stdout.txt` and
`_scheduler-stderr.txt` of its own. Everything lands on the `retrieved`
`FolderData`, in the database, permanently.

## 6. The parser classifies and extracts

The plugin's second job, and it is deliberately in this order:

1. **Are the two essential files there?** No → exit code 300, stop.
2. **What does `dftb.out` say?** `_detect_exit_code` looks for failure
   signatures — SCC first, geometry second, generic `ERROR!` last. Non-zero →
   log at the right severity and return that exit code, attaching no results.
3. **Extract.** Only on a clean run: `_parse_detailed` pulls the scalars out of
   `detailed.out` and they are attached as `output_parameters`.

Both steps 2 and 3 are pure static methods over strings. They can be tested
without AiiDA, without a database and without DFTB+ — which is why most of the
test suite needs none of those.

## 7. You have a result

```python
node.exit_status                                # 0
node.outputs.output_parameters.get_dict()       # the scalars
node.outputs.retrieved.list_object_names()      # every file
node.inputs.parameters.get_dict()               # exactly what went in
```

And the graph that connects them, for as long as the database exists.

## What the plugin never does

Worth stating, because it explains the size of the package:

- It does not talk to the scheduler, the transport or the database.
- It does not decide *when* to run, retry or give up.
- It does not validate DFTB+ settings beyond top-level block names.
- It does not create structure nodes, plot anything, or convert formats.

It answers two questions for AiiDA — *what files does this job need?* and *what
do these output files mean?* — and AiiDA does everything else.
