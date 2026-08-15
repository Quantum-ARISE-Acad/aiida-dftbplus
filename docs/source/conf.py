"""Sphinx configuration for the aiida-dftbplus documentation.

The toolchain is Sphinx + MyST (pages are Markdown), with the API reference
generated from NumPy-style docstrings by autodoc/autosummary. Nothing in the
API reference is hand-written: if something is missing from the rendered site,
the fix is a docstring in ``src/aiida_dftbplus``, not a page here.

Build it with::

    pip install -e . --group docs
    make -C docs           # strict: warnings are errors

Set ``DOCS_OFFLINE=1`` to skip the intersphinx inventory downloads when
building without a network connection. CI never sets it, so a broken
cross-reference still fails the build there.
"""

import os
import time

import aiida_dftbplus
from aiida import load_profile
from aiida.storage.sqlite_temp import SqliteTempBackend

# -- AiiDA setup --------------------------------------------------------------
# autodoc imports the plugin, and the ``aiida-calcjob`` directive instantiates
# its process spec — both need a loaded profile. A throwaway in-memory sqlite
# profile keeps the docs build free of any database service.
load_profile(SqliteTempBackend.create_profile("docs-temp-profile"), allow_switch=True)

# -- Project information ------------------------------------------------------

project = "aiida-dftbplus"
copyright_first_year = "2026"
copyright_owners = "Quantum ARISE, AMUZUGA Wisdom, LABBAH Elie"

current_year = str(time.localtime().tm_year)
copyright_year_string = (
    current_year if current_year == copyright_first_year else f"{copyright_first_year}-{current_year}"
)
# pylint: disable=redefined-builtin
copyright = f"{copyright_year_string}, {copyright_owners}. All rights reserved"
author = copyright_owners

release = aiida_dftbplus.__version__
version = ".".join(release.split(".")[:2])

# -- General configuration ----------------------------------------------------

extensions = [
    # Markdown authoring
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
    # API reference, generated from the source
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
    "sphinx.ext.viewcode",
    # Cross-project links, maths, diagrams
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "sphinx.ext.graphviz",
    # AiiDA's own directives: ``aiida-calcjob`` renders a process spec
    "aiida.sphinxext",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

master_doc = "index"
language = "en"
pygments_style = "sphinx"
pygments_dark_style = "monokai"

# -- MyST ---------------------------------------------------------------------

# ``.rst`` comes first deliberately: autosummary writes its generated stubs with
# the first suffix in this mapping, and those stubs are reStructuredText
# templates. With ``.md`` first they are written as ``.md`` and parsed as
# Markdown, which silently produces an API reference with no documented objects.
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

myst_enable_extensions = [
    "colon_fence",  # ::: fences, so directives survive Markdown editors
    "deflist",
    "fieldlist",
    "attrs_inline",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3
myst_substitutions = {"version": release}

# -- autodoc / autosummary ----------------------------------------------------

autosummary_generate = True
autosummary_imported_members = False

# aiida-core >= 2.9 attaches a family of generated pydantic models to every Node
# subclass (``Model``, ``WriteModel``, ``AttributesModel``, ...). They carry
# ``__module__ = 'aiida_dftbplus.data'``, so autodoc takes them for this plugin's
# own API and — with ``undoc-members`` — documents them, annotations included.
# ``WriteModel.attributes: AttributesWriteModel`` then points at a target that
# exists in no inventory, which ``-nW`` turns into a build failure. None of these
# models is part of the plugin's interface, so they are excluded outright rather
# than silenced with a nitpick exemption.
AIIDA_GENERATED_MODELS = (
    "Model, BaseNodeModel, ReadModel, WriteModel, AttributesModel, "
    "AttributesWriteModel, CliModel, ConstructorModel, ConstructorArgsModel"
)

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "member-order": "bysource",
    "exclude-members": AIIDA_GENERATED_MODELS,
}
# The plugin's private helpers (``_dict_to_hsd``, ``_detect_exit_code``, ...)
# carry the load-bearing logic and are documented deliberately; they are listed
# explicitly in the reference pages rather than swept in wholesale.
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented_params"
autodoc_class_signature = "separated"
autodoc_member_order = "bysource"
autodoc_mock_imports = []

# sphinx-autodoc-typehints
always_document_param_types = False
typehints_use_signature = False
typehints_use_signature_return = False

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True

# -- intersphinx --------------------------------------------------------------

# ASE is deliberately absent: since the ASE documentation moved to ase-lib.org
# it no longer publishes a reachable ``objects.inv``, so an entry here would
# only add a failing inventory fetch to every build. ASE is linked by URL where
# the docs mention it.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "aiida": ("https://aiida.readthedocs.io/projects/aiida-core/en/latest", None),
    "numpy": ("https://numpy.org/doc/stable", None),
    "pymatgen": ("https://pymatgen.org", None),
}
intersphinx_timeout = 30

if os.environ.get("DOCS_OFFLINE"):
    # Building on a machine with no network: drop the mappings entirely rather
    # than let every inventory fetch emit a warning that ``-W`` turns fatal.
    intersphinx_mapping = {}

# -- Nit-picky mode -----------------------------------------------------------

# Base classes and annotations resolve to private, fully qualified module paths
# (``aiida.orm.nodes.data.dict.Dict``) while aiida's object inventory only lists
# the public re-exports (``aiida.orm.Dict``), so intersphinx cannot match them.
nitpick_ignore = [
    ("py:class", "Logger"),
    ("py:class", "QbFields"),
    ("py:class", "AiidaLoggerType"),
    ("py:class", "voluptuous.schema_builder.Schema"),
    ("py:exc", "voluptuous.Invalid"),
    ("py:class", "voluptuous.Invalid"),
]
nitpick_ignore_regex = [
    # Every role, not just py:class: functions and exceptions such as
    # ``aiida.common.utils.validate_list_of_string_tuples`` and
    # ``aiida.common.exceptions.ParsingError`` are equally absent from the
    # published inventory under their private paths.
    ("py:.*", r"aiida\..*"),
    ("py:.*", r"plumpy\..*"),
    ("py:.*", r"click\..*"),
    ("py:.*", r"voluptuous\..*"),
]

# -- HTML output --------------------------------------------------------------

# pydata-sphinx-theme rather than furo: it is the visual language of the
# scientific Python ecosystem (numpy, pandas, ASE-adjacent projects), it ships a
# light/dark toggle, and its top navbar keeps the four Diataxis sections visible
# from every page.
html_theme = "pydata_sphinx_theme"
html_title = f"aiida-dftbplus v{release}"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_show_sourcelink = False
html_search_language = "en"
html_use_opensearch = "https://aiida-dftbplus.readthedocs.io/en/latest"

html_theme_options = {
    "github_url": "https://github.com/Quantum-ARISE-Acad/aiida-dftbplus",
    "icon_links": [
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/aiida-dftbplus/",
            "icon": "fa-brands fa-python",
        },
        {
            "name": "AiiDA",
            "url": "https://www.aiida.net",
            "icon": "fa-solid fa-atom",
        },
    ],
    "navbar_align": "left",
    "show_toc_level": 2,
    "navigation_with_keys": False,
    "footer_start": ["copyright"],
    "footer_end": ["sphinx-version"],
    "external_links": [
        {"name": "DFTB+", "url": "https://dftbplus.org"},
        {"name": "SKF parameter sets", "url": "https://dftb.org/parameters"},
    ],
}

html_context = {
    "github_user": "Quantum-ARISE-Acad",
    "github_repo": "aiida-dftbplus",
    "github_version": "main",
    "doc_path": "docs/source",
    "default_mode": "auto",
}

# -- Graphviz -----------------------------------------------------------------

# SVG keeps the diagrams sharp at any zoom and lets them inherit a transparent
# background, which is what makes one rendering work in both colour themes.
graphviz_output_format = "svg"
graphviz_dot_args = ["-Gbgcolor=transparent"]

# -- linkcheck ----------------------------------------------------------------

linkcheck_ignore = [
    r"http://localhost:\d+/?",
    r"https://pypi\.org/project/aiida-dftbplus.*",  # not published yet
    r"https://test\.pypi\.org/.*",
    r"https://quantum-arise-acad\.github\.io/.*",  # only live after first deploy
    r".*/objects\.inv$",
]
linkcheck_retries = 2
linkcheck_timeout = 30
linkcheck_anchors = False
