# Architecture

This section is written for maintainers. It should let you understand the whole
package — what each module is responsible for, what it must never do, and why
the load-bearing decisions were made — without reading all the source.

The package is small: five modules, about 700 lines of source, four entry
points, one `CalcJob`, one `Parser`, one `Data` class, one CLI group.

```{toctree}
:maxdepth: 1

module-map
entry-points
lifecycle
io-contract
design-decisions
contributing
```

## Where this plugin sits

```{graphviz} ../_static/diagrams/ecosystem.dot
:caption: aiida-dftbplus in the AiiDA ecosystem — the plugin is code that runs inside the daemon worker.
:align: center
```

Everything else in that picture is infrastructure the plugin borrows from AiiDA.
The plugin itself never talks to the scheduler, the transport, or the database.
It answers two questions for AiiDA — *what files does this job need?* and *what
do these output files mean?* — and AiiDA does the rest. That is why the whole
package fits in five modules.
