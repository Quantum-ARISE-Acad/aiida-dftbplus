# Releasing

## How the pipeline is put together

| Workflow | Runs on | Does |
|---|---|---|
| `ci.yml` | pull requests, and called by `release.yml` | lint, SAST, dependency review, build, tests, integration test, docs |
| `release.yml` | push to `main`, tags `v*`, manual dispatch | runs `ci.yml`, then publishes |
| `codeql.yml` | push, pull requests, weekly | GitHub code scanning |
| `docs.yml` | push to `main`, tags `v*`, manual, weekly | builds the Sphinx site and deploys it to GitHub Pages; the weekly run is a link check only |

`ci.yml` has no push trigger of its own — `release.yml` calls it, so a push to
`main` runs every gate exactly once, and the artifact that gets published is the
same one the tests ran against.

Branch protection should require the single **`ci success`** job, which is green
only when every other job is.

Two of the gates are deliberately not blocking:

* **pip-audit** reports known CVEs in the dependency tree to the job summary,
  but does not fail the build. Nearly all findings live in transitive
  dependencies of `aiida-core` and often have no fix this project can apply.
  New risky dependencies are still blocked on pull requests by the
  `dependency review` job.
* **Coveralls upload** is best-effort, so a coverage service outage cannot
  block a release.

## One-time setup

### 1. PyPI Trusted Publishing

No API token is stored in this repository — PyPI verifies a short-lived OIDC
token issued by GitHub instead. Register the publisher on both indexes:

* <https://pypi.org/manage/account/publishing/>
* <https://test.pypi.org/manage/account/publishing/>

with:

| Field | Value |
|---|---|
| PyPI project name | `aiida-dftbplus` |
| Owner | `Quantum-ARISE-Acad` |
| Repository | `aiida-dftbplus` |
| Workflow name | `release.yml` |
| Environment | `pypi` (and `testpypi` on TestPyPI) |

For a project that does not exist on the index yet, use the *pending publisher*
form — the project is created on first upload.

Once this is in place the old `pypi_token` repository secret is unused and
should be deleted from **Settings → Secrets and variables → Actions**.

### 2. GitHub Pages

Under **Settings → Pages**, set the source to **GitHub Actions**. `docs.yml`
then publishes to <https://quantum-arise-acad.github.io/aiida-dftbplus/> on
every push to `main`. Pull requests are not deployed — they are only built, by
the `docs` job in `ci.yml`, with warnings treated as errors.

### 3. GitHub environments

Create two environments under **Settings → Environments**: `pypi` and
`testpypi`. Add required reviewers to `pypi` if uploads should need a human
approval; everything else works without further configuration.

### 3. Branch protection

Protect `main` and set **`ci success`** as the only required status check. That
single job aggregates lint, SAST, build, test, integration and docs, so the
list does not have to be maintained as jobs are added.

## Cutting a release

1. Bump the version — it lives in one place:

   ```shell
   hatch version 0.2.0     # or: minor / patch / a / b / rc
   ```

2. Commit, push, and let CI go green on `main`. That push also uploads the
   build to TestPyPI, so the artifact can be installed and checked before the
   real thing:

   ```shell
   pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple aiida-dftbplus
   ```

3. Tag and push. The tag must match `__version__`; the pipeline refuses to
   publish otherwise.

   ```shell
   git tag -a v0.2.0 -m "Release v0.2.0"
   git push origin v0.2.0
   ```

The tag push then runs the whole CI suite again, publishes to PyPI, attaches a
signed build-provenance attestation, and opens a GitHub release with
auto-generated notes and the distribution files attached.

`workflow_dispatch` on the **release** workflow does the same on demand, with
the target index as an input — useful for a dry run against TestPyPI.

## Running the gates locally

```shell
hatch fmt --check          # lint + format, the same command CI runs
hatch run security:all     # bandit + pip-audit
hatch test --cover         # test suite with coverage
hatch run docs:build       # docs, with warnings treated as errors
hatch build                # sdist + wheel
```

The end-to-end test is skipped unless a `dftb+` binary is on `PATH`; CI runs it
in the `integration` job with DFTB+ installed from conda-forge.
