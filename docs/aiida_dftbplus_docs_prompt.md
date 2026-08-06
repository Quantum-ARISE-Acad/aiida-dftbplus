# Claude Code prompt — build the documentation site for `aiida-dftbplus`

## The task

Build a complete, professional documentation website for the `aiida-dftbplus` package,
hosted on GitHub Pages, that meets the standard set by leading computational materials
science packages — AiiDA, PyXtal, SMACT, pymatgen, ASE.

The site must take a reader from "I have never used this plugin" to "I can write my own
advanced workflow with it," through tutorials, how-to guides, a complete architectural
description, and a full auto-generated API reference.

---

## Before writing anything (mandatory)

1. Read the entire package source. Inventory every public module, class, function, and
   entry point. Note which are `CalcJob`s, `Parser`s, `Data` types, `WorkChain`s, and
   which are internal helpers.
2. Read `pyproject.toml` / `setup.cfg` — capture the real package name, version, Python
   requirement, dependencies, and especially the **AiiDA entry points** registered under
   `aiida.calculations`, `aiida.parsers`, `aiida.data`, `aiida.workflows`.
3. Read existing `README.md`, `CLAUDE.md`, `ARCHITECTURE.md`, any `examples/`, and the
   test suite — tests are the most honest description of how the package is actually
   used, and are the best source for tutorial material.
4. Check whether any `docs/` directory already exists and report its state.
5. Produce a **complete proposed site map** (every page, its title, and a one-line
   description of its content) plus the chosen toolchain, and **stop for my approval**.
   Do not scaffold or write a single page before the site map is approved.

Report honestly anything you find that contradicts this prompt rather than working
around it silently.

---

## Toolchain — non-negotiable choices and why

**Use Sphinx, not MkDocs.** This is deliberate and must not be substituted. The
computational materials ecosystem — AiiDA, pymatgen, ASE, PyXtal — standardised on
Sphinx, and the decisive feature is **intersphinx**: it lets this plugin's documentation
cross-link directly into AiiDA's own API reference, so a reference to `orm.StructureData`
in our docs becomes a live link into AiiDA's docs. An AiiDA plugin whose docs cannot
cross-link into AiiDA is a plugin that reads as disconnected from its ecosystem.

Required stack:

- **Sphinx** as the generator.
- **MyST parser**, so pages are authored in Markdown rather than reStructuredText.
- **sphinx-autodoc** + **sphinx-autosummary** for the API reference generated from
  docstrings — never hand-written and never allowed to drift.
- **napoleon** for docstring parsing. Use **NumPy-style docstrings**, the scientific
  Python convention, and apply it consistently across the whole package.
- **sphinx-autodoc-typehints**, so type information lives in the code's annotations and
  is rendered into the docs without being duplicated in prose.
- **intersphinx**, wired to AiiDA, Python, NumPy, and pymatgen/ASE where the package
  touches them.
- **sphinx-copybutton** on all code blocks.
- **myst-nb** if any tutorial is best expressed as an executed notebook.
- **furo** or **pydata-sphinx-theme** for the theme — pick one, justify it in one line,
  and be consistent. (pydata-sphinx-theme is the closer match to the scientific
  ecosystem's visual language.)
- Docs dependencies go in a **`[dependency-groups]` docs group** in `pyproject.toml`,
  isolated from runtime dependencies. The docs toolchain must never leak into what a
  user installs.

---

## Site structure — the four-quadrant model

Organise the site by the Diátaxis model, because mixing these four modes is the single
most common failure in scientific package docs. Each quadrant answers a different
question and must not bleed into the others.

```
                 Learning-oriented    │  Task-oriented
                 ─────────────────────┼──────────────────────
   Practical     TUTORIALS            │  HOW-TO GUIDES
                 "teach me"           │  "help me do X"
                 ─────────────────────┼──────────────────────
   Theoretical   EXPLANATION          │  REFERENCE
                 "help me understand" │  "tell me exactly"
```

### Required top-level sections

**1. Home / landing page**
What the package is in two sentences, what it does for the reader, a 10-line
copy-pasteable example that actually runs, install command, and clear links into the four
sections below. A reader must understand the package's purpose within 15 seconds.

**2. Getting started**
- Installation — pip, from source, and the development install, each verified.
- Prerequisites, stated honestly: a working AiiDA profile, a configured `Computer`, a
  DFTB+ binary, and Slater–Koster parameter files. Say plainly that this plugin cannot
  work without them and link to AiiDA's own setup docs via intersphinx.
- Configuring the DFTB+ `Code` in AiiDA (`verdi code create`), with a full worked example.
- Where to get SKF parameter sets and how to point the plugin at them.
- A **"your first calculation"** page: from a fresh profile to a completed DFTB+ run and
  its parsed results, with the expected output shown at each step.
- A verification checklist: the exact commands that prove the install works before the
  reader continues.

**3. Tutorials — learning-oriented, sequential, guaranteed to work**
Each tutorial is a complete narrative with a stated goal, prerequisites, every step, the
expected output at each step, and a "what you learned" close. Tutorials must be
**runnable end to end** and tested. Required progression:
- T1 — a single-point energy calculation on a simple crystal.
- T2 — geometry relaxation, and reading the relaxed structure back.
- T3 — a band structure or DOS calculation (whatever the package supports).
- T4 — running a `WorkChain`: submitting, monitoring with `verdi process list`, and
  retrieving results.
- T5 — a high-throughput run over many structures, showing how AiiDA's provenance graph
  captures the whole campaign.
- T6 — writing a custom `WorkChain` on top of the plugin's `CalcJob`.

**4. How-to guides — task-oriented, short, assume competence**
Each answers exactly one question with no narrative padding. At minimum:
- How to set custom DFTB+ input parameters.
- How to choose and configure SKF parameter sets.
- How to run on a remote machine / HPC scheduler.
- How to restart a failed or unconverged calculation.
- How to control SCC convergence and diagnose non-convergence.
- How to query results with the `QueryBuilder`.
- How to export structures and results to CIF / pymatgen / ASE.
- How to handle common errors — one section per real error the parser can emit.

**5. Explanation / topic guides — understanding-oriented**
- How the plugin works: the full path from a Python `builder` to a running DFTB+ job and
  back to parsed `Data` nodes.
- Why the `CalcJob` / `Parser` split exists and what each is responsible for.
- The data model — which AiiDA node types are produced, and what each carries.
- Provenance — what the plugin records and how to trace a result back to its inputs.
- Error handling and the restart/recovery philosophy.
- A short, honest primer on DFTB+ itself: what DFTB is, what it is good for, and where
  its approximations break down. Do not oversell the method.

**6. Architecture — the complete structural description**
This section must let a new contributor understand the whole package without reading all
the source. Include:
- A module-by-module map: every module, its responsibility, and what it must never do.
- The full entry-point table (entry point name → class → what it does), since entry
  points are how AiiDA discovers a plugin and are frequently under-documented.
- The lifecycle of a calculation as a sequence: builder → `prepare_for_submission` →
  input file generation → scheduler submission → retrieval → `parse` → output nodes.
- The input/output node contract: every input port and output node, with type and
  whether it is required.
- Design decisions and their rationale — the "why it is built this way" that a reader
  cannot recover from the code.
- A contributing guide: dev install, running tests, code style, docstring conventions,
  how to add a new parser or calculation type.

**7. API reference — fully auto-generated**
Generated by autodoc/autosummary from NumPy-style docstrings. Every public class,
method, and function documented with parameters, types, returns, raises, and a short
usage example where non-obvious. Source links enabled. **Nothing in the API reference
is hand-written** — if it is missing from the rendered output, the fix is a docstring in
the source, not a page in the docs.

**8. Supporting pages**
- Changelog (from `CHANGELOG.md`).
- Citation / "how to cite" — with a BibTeX block. Scientific users need this and its
  absence signals an unserious package.
- License.
- Acknowledgements and funding.

---

## Diagrams

The architecture section must be visual, not only prose. Generate diagrams
programmatically so they can be regenerated when the code changes, and commit the
generating scripts under `docs/diagrams/`. Use Graphviz (via Sphinx's `graphviz`
extension) or the `diagrams` library, and matplotlib for anything chart-like.

Required diagrams:
1. **Calculation lifecycle** — builder → submission → execution → retrieval → parsing →
   output nodes.
2. **The provenance graph** a single calculation produces, showing real node types.
3. **Module dependency map** of the package.
4. **The input/output node contract** — what goes in, what comes out, what is optional.
5. **Where this plugin sits in the AiiDA ecosystem** — daemon, database, scheduler,
   remote computer, and this plugin's place among them.

Diagrams must be legible in both light and dark theme, use one consistent colour meaning
across all five, and never rely on colour alone to distinguish categories.

---

## Docstring pass (a required sub-task, not optional)

The API reference is only as good as the docstrings. As an explicit early sub-task,
audit every public object and bring its docstring to NumPy style with: a one-line
summary, an extended description where warranted, `Parameters`, `Returns`, `Raises`,
and an `Examples` block for anything whose usage is not obvious.

**Do not change any code behaviour during this pass** — docstrings and type annotations
only. If a docstring cannot be written truthfully because the function's behaviour is
unclear, flag it to me rather than inventing a description.

---

## Quality bar — measured against the ecosystem

Study how AiiDA, PyXtal, SMACT, and pymatgen structure their documentation and match
that standard. Concretely, the site must satisfy all of the following:

- A new user reaches a **working first calculation in under 10 minutes** of reading.
- **Every code example runs.** No pseudo-code, no `...`, no fragments that would fail if
  pasted. If an example needs a structure file, ship it in the docs.
- **Every public API object appears** in the reference with a real docstring.
- Prerequisites, limitations, and known failure modes are stated **plainly and early** —
  never buried or omitted. An honest limitations section builds far more trust than a
  page of claims.
- Cross-references to AiiDA, ASE, and pymatgen resolve as **live intersphinx links**.
- The site is **searchable**, mobile-readable, and works in light and dark themes.
- Nothing on the site contradicts the code. If prose and code disagree, the code wins
  and the prose is fixed.

---

## Hosting and automation

- Publish to **GitHub Pages** via a GitHub Actions workflow (`.github/workflows/docs.yml`)
  that builds the Sphinx site and deploys it — either with `peaceiris/actions-gh-pages`
  or the official Pages actions. Pin actions to a tag or SHA rather than a branch.
- Build docs on **every pull request** (build only, no deploy) so a broken docs build
  fails CI before merge. Deploy only from the default branch and from release tags.
- Treat **Sphinx warnings as errors** (`-W`) in CI, so a broken cross-reference or a
  missing docstring reference cannot land silently.
- Add a **link checker** (`sphinx.ext.linkcheck`) on a schedule, so dead external links
  surface without blocking normal builds.
- Ensure a `.nojekyll` file is present so GitHub Pages does not strip Sphinx's
  underscore-prefixed asset directories.
- Add the docs badge and link to `README.md`.
- Optionally configure `.readthedocs.yaml` as well, so the project can move to or mirror
  on Read the Docs for versioned URLs without rework.

---

## How to work — approval-gated, one sub-task at a time

1. Read the package (mandatory section above).
2. Present the **complete site map + chosen theme**. **Stop for approval.**
3. **Sub-task A** — scaffold: `docs/` skeleton, `conf.py` with every extension wired,
   the docs dependency group, and a minimal build that succeeds. Gate: `sphinx-build -W`
   passes with an empty-but-valid site.
4. **Sub-task B** — the docstring pass. Gate: `-W` build produces a complete API
   reference with no missing-reference warnings; test suite still green; no behaviour
   changed.
5. **Sub-task C** — the diagram scripts, rendered and reviewed **before** prose is
   written around them. Gate: all five diagrams render and are legible in both themes.
6. **Sub-task D** — Getting started + Tutorials. Gate: every example verified to run.
7. **Sub-task E** — How-to guides + Explanation + Architecture.
8. **Sub-task F** — the Actions workflow, Pages deployment, badges, and supporting pages.
   Gate: the site is live and every internal link resolves.

After each sub-task: run the docs build with warnings-as-errors, run the test suite, and
**stop for my review before starting the next**. Do not batch sub-tasks.
