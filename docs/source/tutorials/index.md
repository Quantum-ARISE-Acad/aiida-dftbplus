# Tutorials

Learning-oriented lessons, meant to be worked through in order. Each one states
its goal and prerequisites, shows every command, shows the output you should
see, and closes with what you learned.

Every tutorial here runs against the `mio-1-1` Slater–Koster set on a localhost
computer, so none of them needs an HPC account. If you have not set that up yet,
do [Getting started](../getting-started/index.md) first.

```{toctree}
:maxdepth: 1

t1-single-point
t2-relaxation
t3-band-structure
t4-submit-monitor
t5-high-throughput
t6-custom-workchain
```

## What each tutorial covers

| Tutorial | You will learn |
| --- | --- |
| [T1](t1-single-point.md) | Build a parameter dictionary, run a single-point energy, read the parsed output |
| [T2](t2-relaxation.md) | Add a `Driver` block, relax a geometry, read the relaxed structure back out |
| [T3](t3-band-structure.md) | Request eigenvalues, retrieve `band.out`, and plot it yourself — the plugin does not parse it |
| [T4](t4-submit-monitor.md) | Submit to the daemon instead of blocking, monitor with `verdi process list`, diagnose a failure |
| [T5](t5-high-throughput.md) | Run a campaign over many structures, reuse SKF nodes, collect results with the `QueryBuilder` |
| [T6](t6-custom-workchain.md) | Write your own `WorkChain` on top of the plugin's `CalcJob`, since the plugin ships none |

:::{note}
Tutorial T3 and T6 document deliberate gaps in the plugin: there is no band
structure parser and there are no workflows. Both tutorials show what to do
about that rather than pretending otherwise.
:::
