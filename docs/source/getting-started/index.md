# Getting started

This section takes you from nothing to a completed DFTB+ calculation with parsed
results. Work through it in order — each page assumes the one before it.

The honest summary of what you need: **an AiiDA profile, a configured
`Computer`, a DFTB+ binary, and Slater–Koster parameter files**. This plugin
cannot do anything without all four, and it will not obtain any of them for you.

```{toctree}
:maxdepth: 1

prerequisites
installation
configure-code
skf-parameter-sets
first-calculation
verification
```

## The short version

For readers who already run AiiDA and just want the plugin wired up:

```shell
pip install aiida-dftbplus
verdi plugin list aiida.calculations           # 'dftbplus' must appear
verdi code create core.code.installed \
    --label dftb+ --computer localhost \
    --default-calc-job-plugin dftbplus \
    --filepath-executable "$(which dftb+)" \
    --non-interactive
```

Then jump to [Your first calculation](first-calculation.md). If any of those
commands is unfamiliar, start at [Prerequisites](prerequisites.md) instead.
