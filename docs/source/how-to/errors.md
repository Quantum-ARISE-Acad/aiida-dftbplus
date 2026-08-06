# Handle common errors

One section per failure this plugin can produce, with the diagnosis and the fix.
The exit-code table itself is in [Exit codes](../reference/exit-codes.md).

Start every diagnosis the same way:

```shell
verdi process report <PK>
verdi calcjob outputcat <PK> dftb.out | tail -30
verdi calcjob outputcat <PK> _scheduler-stderr.txt
```

---

## 300 — `ERROR_MISSING_OUTPUT`

> `dftb.out or detailed.out was not retrieved from the remote.`

DFTB+ produced no usable output, so nothing can be said about the run. The cause
is outside DFTB+ almost every time.

**Check, in order:**

1. `_scheduler-stderr.txt` in `retrieved` — walltime kill, out-of-memory kill,
   `module: command not found`.
2. `verdi calcjob gotocomputer <PK>` — is the working directory there, and what
   is in it?
3. The executable path: `verdi code show <code>` and check it exists on that
   machine.
4. Disk quota on the scratch filesystem.

**Fixes:** raise `max_wallclock_seconds`; request more memory; put the
`module load` in the code's `prepend_text`; fix the path.

---

## 310 — `ERROR_DFTB_FAILED`

> `DFTB+ reported a fatal ERROR in dftb.out.`

DFTB+ started and stopped deliberately. The message names the reason:

```shell
verdi calcjob outputcat <PK> dftb.out | grep -B 3 -A 6 "ERROR"
```

Common ones:

**Cannot open an SKF file**
: A missing element pair or a `Prefix` without its trailing slash. Both
  orderings must exist (`O-S.skf` *and* `S-O.skf`). See
  [SKF sets](../getting-started/skf-parameter-sets.md).

**Unknown keyword / unparsed block**
: A typo inside a block — the plugin validates only top-level block names. The
  message gives the path and the line in `dftb_in.hsd`. Compare with
  `verdi calcjob inputcat <PK> dftb_in.hsd`.

**Missing `MaxAngularMomentum` for an element**
: Every element in the structure needs an entry. This is not optional.

**Empty stdout**
: The plugin also returns 310 when `dftb.out` is empty — the process died before
  writing anything. Treat it like a 300 and look at the scheduler files.

---

## 320 — `ERROR_SCC_NOT_CONVERGED`

> `SCC self-consistency cycle did not converge.`

The calculation ran; the charges did not converge within `MaxSCCIterations`.
Logged as a **warning**, because the run is usable and the failure is
recoverable. `output_parameters` is not attached, deliberately.

Full treatment in [Control SCC convergence](scc-convergence.md); the automated
retry is [T6](../tutorials/t6-custom-workchain.md).

:::{note}
DFTB+ prints `ERROR!` on the line immediately before `SCC is NOT converged`. The
parser checks the convergence message **first**, which is why this comes back as
a recoverable 320 rather than a fatal 310. If you ever see one of these
classified as 310, that ordering has regressed — there is a test for it.
:::

---

## 330 — `ERROR_GEOMETRY_NOT_CONVERGED`

> `Geometry relaxation did not converge within MaxSteps.`

The relaxation used up its step budget. `geom.out.gen` holds the last geometry,
so continuing is cheap — see [Restart](restart.md).

If it will not converge at all with more steps:

- **A soft mode** — a floppy molecule, a nearly flat surface. Loosen
  `MaxForceComponent`.
- **A bad starting geometry.** Pre-relax with something cheaper.
- **Wrong parameters for the chemistry.** No optimiser fixes that.

---

## Finished `[0]` but the numbers are wrong

The parser reports "no known failure signature". It cannot tell you the physics
is wrong. Suspect the parameter set first:

- wrong set for the chemistry;
- files from two sets mixed;
- `MaxAngularMomentum` not matching the set;
- a DFTB3 set used without `ThirdOrderFull` and `HubbardDerivs`.

See [SKF sets](../getting-started/skf-parameter-sets.md).

---

## `output_parameters` is missing a key

Not an error. `_parse_detailed` reports what it finds:

- `fermi_energy_eV` — absent when DFTB+ printed no Fermi level, which is normal
  for a non-periodic system;
- `forces_eV_Ang` and `max_force_eV_Ang` — absent unless forces were requested
  (`Analysis { CalculateForces = Yes }`);
- `n_scc_iterations` — absent with recent DFTB+ versions, which no longer print
  the line the parser looks for. See
  [known parsing gaps](../reference/exit-codes.md#known-parsing-gaps).

Everything is still in `detailed.out` on the `retrieved` node.

---

## `Excepted` instead of `Finished`

An exception was raised in the plugin or the engine, not in DFTB+. This is a
bug, or a malformed input the validator did not catch.

```shell
verdi process report <PK>       # the traceback is here
```

Known one, fixed but worth recognising: `PluginInternalError: local_copy_list
format problem` came from `None` paths in the copy list. If you see an
exception, the traceback names the module — [open an
issue](https://github.com/Quantum-ARISE-Acad/aiida-dftbplus/issues) with it.

---

## The daemon stops responding during a batch

`verdi daemon status` times out; jobs sit in `Waiting`. The workers are almost
certainly blocked copying files, not computing. This is the failure mode of
uploading a full SKF set with every job — 5625 files and 1.5 GB per calculation
against 0.79 s of DFTB+ time.

```shell
ps -o pid,stat,wchan:24,cmd -p $(pgrep -f "verdi.*daemon")   # 'D' = uninterruptible disk wait
```

Fix: ship only the element pairs the run needs, or switch to
`use_remote_skf_path=True`. See
[the SKF performance warning](../getting-started/skf-parameter-sets.md#ship-only-what-the-run-reads).

---

## Submission fails before anything runs

**`One of 'parameters' or 'dftb_input' is required.`**
: Neither input was given. The validator catches it before submission on
  purpose — the alternative is an empty `dftb_in.hsd` failing on a remote
  machine minutes later.

**`Provide either 'parameters' or 'dftb_input', not both.`**
: Exactly one.

**`'Hamiltoniann' is not a known top-level DFTB+ block`**
: A typo caught by `DftbParameters`. The message lists the allowed blocks;
  prefix a key with `_raw` to pass it through untouched.

**`unsupported metadata key: options`** (in your own WorkChain)
: `expose_inputs` without a namespace collided with the workchain's own
  `metadata` port. Use `spec.expose_inputs(DftbPlusCalculation,
  namespace="dftb")` — see [T6](../tutorials/t6-custom-workchain.md).
