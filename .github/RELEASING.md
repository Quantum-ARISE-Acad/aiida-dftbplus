# Releasing

## How the pipeline is put together

| Workflow | Runs on | Does |
|---|---|---|
| `ci.yml` | pull requests, and called by `release.yml` | lint, SAST, dependency review, build, tests, integration test, docs |
| `release.yml` | push to `main`, tags `v*`, manual dispatch | runs `ci.yml`, then publishes |
| `codeql.yml` | push, pull requests, weekly | GitHub code scanning |
| `docs.yml` | manual, weekly | external link check only — the site itself is built and published by Read the Docs |

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

### 2. Read the Docs

The documentation lives at <https://aiida-dftbplus.readthedocs.io/>. Read the
Docs builds it from its own webhook — no GitHub workflow deploys anything, and
nothing here needs a token.

Import the project once at <https://readthedocs.org/dashboard/import/>. The
build is described entirely by `.readthedocs.yml` — one of the alternate
filenames Read the Docs still auto-detects; rename it to `.readthedocs.yaml` if
that ever stops being true. Enable **Admin → Settings → Build pull requests for
this project** if preview builds are wanted.

`.readthedocs.yml` sets `fail_on_warning: true`, the same rule the `docs` job in
`ci.yml` applies on every pull request, so a broken cross-reference fails before
it can reach the published site.

### 3. GitHub environments

Create two environments under **Settings → Environments**: `pypi` and
`testpypi`. Add required reviewers to `pypi` if uploads should need a human
approval; everything else works without further configuration.

### 4. Branch protection

Protect `main` and set **`ci success`** as the only required status check. That
single job aggregates lint, SAST, build, test, integration and docs, so the
list does not have to be maintained as jobs are added.

## Troubleshooting the first release

The first of these is a setup step that has not been done yet, not a fault in
the workflows: it needs no code change and no new tag.

### `invalid-publisher`: valid token, but no corresponding publisher

```text
Error: Trusted publishing exchange failure:
* `invalid-publisher`: valid token, but no corresponding publisher
```

PyPI received a correctly signed token from GitHub and found nothing registered
to accept it — step 1 above has not been done, or one of its five fields does
not match exactly. The claims printed under the error are what PyPI compared
against; register a **pending publisher** with precisely those values:

| Field on PyPI | Value | Where the claim comes from |
|---|---|---|
| PyPI project name | `aiida-dftbplus` | the package name in `pyproject.toml` |
| Owner | `Quantum-ARISE-Acad` | `repository_owner` |
| Repository name | `aiida-dftbplus` | `repository` |
| Workflow name | `release.yml` | the filename in `workflow_ref`, with the extension |
| Environment name | `pypi` | `environment` |

Register the same thing on TestPyPI with the environment `testpypi`, or the
push-to-`main` job fails the same way.

Common mismatches: the full path `.github/workflows/release.yml` in the workflow
field instead of the bare filename; the environment left blank; the publisher
registered under a personal account rather than the organisation that will own
the project.

Nothing was uploaded when this fails, so the version number is still free. After
registering, **re-run the failed jobs** on the same tag from the Actions page —
no need to delete and re-push the tag.

### The Read the Docs build fails while the pull request was green

`.readthedocs.yml` sets `fail_on_warning: true`, so their builder fails on
exactly what `-nW` fails on locally. The usual cause is a dependency that moved
underneath the docs rather than anything in the pull request: Read the Docs
resolves the toolchain and `aiida-core` afresh on every build, so a new release
can introduce a cross-reference target that did not exist when CI last ran.

Reproduce it the way their builder sees it — a fresh environment and a clean
build, because an incremental one hides autodoc warnings:

```shell
hatch env remove docs
hatch run docs:rebuild
```

### `Node 20 is being deprecated`

Informational, from the runner, not a failure. It reports that an action still
declares Node 20 while the runner now defaults to Node 24. No action needed;
it will disappear when the action publishes a new major version.

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
