# Makefile for the aiida-dftbplus documentation.
#
# The default target is deliberately the strict one: warnings are errors, so a
# broken cross-reference or a missing docstring reference fails here rather
# than landing silently on the published site.
#
#   make            # strict HTML build (what CI runs)
#   make html       # same, spelled out
#   make fast       # non-strict build, for quick iteration while writing
#   make clean-all  # remove the build dir *and* the generated API stubs
#   make linkcheck  # check every external link (run on a schedule, not as a gate)
#   make view       # open the built site in a browser

SPHINXBUILD   = sphinx-build
SOURCEDIR     = source
BUILDDIR      = build
SPHINXOPTS    =

# -n  nit-picky: report every unresolvable cross-reference
# -W  turn warnings into errors
# --keep-going: report all of them, not just the first
STRICTOPTS    = -n -W --keep-going

ALLSPHINXOPTS = -d $(BUILDDIR)/doctrees $(SPHINXOPTS) $(SOURCEDIR)

ifeq ($(shell which $(SPHINXBUILD) >/dev/null 2>&1; echo $$?), 1)
$(error The '$(SPHINXBUILD)' command was not found. Install the docs toolchain with `pip install -e . --group docs`, or run `hatch run docs:build`.)
endif

.PHONY: all html fast dirhtml linkcheck clean clean-all view help

all: html

help:
	@echo "html       strict build (warnings are errors) — what CI runs"
	@echo "fast       non-strict build, for iterating on prose"
	@echo "clean-all  remove build/ and the generated API stubs"
	@echo "linkcheck  verify external links"
	@echo "view       open the built site"

html:
	$(SPHINXBUILD) -b html $(STRICTOPTS) $(ALLSPHINXOPTS) $(BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR)/html."

fast:
	$(SPHINXBUILD) -b html $(ALLSPHINXOPTS) $(BUILDDIR)/html

dirhtml:
	$(SPHINXBUILD) -b dirhtml $(STRICTOPTS) $(ALLSPHINXOPTS) $(BUILDDIR)/dirhtml

linkcheck:
	$(SPHINXBUILD) -b linkcheck $(ALLSPHINXOPTS) $(BUILDDIR)/linkcheck

clean:
	rm -rf $(BUILDDIR)

# autosummary writes generated stubs into source/reference/api/_generated; an
# incremental rebuild keeps stale ones and hides warnings CI will catch.
clean-all: clean
	rm -rf $(SOURCEDIR)/reference/api/_generated

view:
	xdg-open $(BUILDDIR)/html/index.html
