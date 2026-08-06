# Releasing

## How the pipeline is put together

| Workflow | Runs on | Does |
|---|---|---|
| `ci.yml` | pull requests, and called by `release.yml` | lint, SAST, dependency review, build, tests, integration test, docs |
| `release.yml` | push to `main`, tags `v*`, manual dispatch | runs `ci.yml`, then publishes |
| `codeql.yml` | push, pull requests, weekly | GitHub code scanning |
| `docs.yml` | push to `main`, manual, weekly | builds the Sphinx site and deploys it to GitHub Pages; the weekly run is a link check only |

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

### 4. Branch protection

Protect `main` and set **`ci success`** as the only required status check. That
single job aggregates lint, SAST, build, test, integration and docs, so the
list does not have to be maintained as jobs are added.

## Troubleshooting the first release

Both of these are setup steps that have not been done yet, not faults in the
workflows. Neither needs a code change or a new tag.

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

### `Failed to create deployment (status: 404)` on Pages

```text
Error: Creating Pages deployment failed
Error: HttpError: Not Found
```

GitHub Pages is not enabled for the repository, so there is nothing to deploy
to. Fix it under **Settings → Pages → Build and deployment** by setting the
source to **GitHub Actions** (step 2 above), then re-run the `docs` workflow.

If Pages is not offered at all, the repository is private and the account plan
does not include Pages for private repositories — either make the repository
public or upgrade the plan.

### `Tag "vX.Y.Z" is not allowed to deploy to github-pages`

```text
Tag "v0.1.0" is not allowed to deploy to github-pages due to environment
protection rules.
```

GitHub creates the `github-pages` environment with a deployment branch policy
that permits the default branch only, so a run triggered by a tag builds fine
and is then refused at the deployment step.

`docs.yml` therefore triggers on pushes to `main` and not on tags. A tag points
at a commit that is already on `main`, so its documentation was published by
that push — there is nothing for a tag run to add.

If you do want tags to publish (a versioned docs scheme, say), add the
permission rather than removing the protection: **Settings → Environments →
`github-pages` → Deployment branches and tags → Add rule**, with a rule of type
**Tag** matching `v*`.

### The deployment sits at `deployment_queued` and is then cancelled

```text
Getting Pages deployment status...
Current status: deployment_queued
... (repeated) ...
Canceling Pages deployment...
Error: The operation was canceled.
```

The deployment was created and accepted — this is not a permissions or content
problem. It means the Pages backend took the deployment and had not finished it
by the time something gave up. If the run ends after almost exactly the job's
`timeout-minutes`, it was the **job timeout** that cancelled it, not the action;
the deployment is then recorded as `error`.

`docs.yml` allows 35 minutes for the deploy job and passes `timeout: 1800000`
to `deploy-pages`, so the action reports its own failure rather than being
killed mid-poll. It also uses a single `concurrency: group: pages`, so two runs
cannot queue deployments against the same site at once.

Inspect what actually happened, rather than re-reading the log:

```shell
gh api repos/Quantum-ARISE-Acad/aiida-dftbplus/pages --jq '{status, build_type, html_url}'
gh api "repos/Quantum-ARISE-Acad/aiida-dftbplus/deployments?environment=github-pages&per_page=3" \
    --jq '.[] | {id, sha: .sha[0:8], created_at}'
gh api repos/Quantum-ARISE-Acad/aiida-dftbplus/deployments/<ID>/statuses \
    --jq '.[] | {state, created_at}'
```

A healthy deployment goes `waiting → queued → in_progress → success` in a minute
or two. `status: null` on the site means it has never completed one.

If it stalls repeatedly with a small artifact, check
<https://www.githubstatus.com> for the **Pages** component and retry — the first
deployment for a brand-new site is the one that most often needs a second
attempt.

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
