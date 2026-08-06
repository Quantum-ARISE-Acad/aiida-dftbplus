#!/usr/bin/env python
"""Generate the documentation diagrams as Graphviz ``.dot`` sources.

Run this whenever the package structure changes::

    python docs/diagrams/generate.py

The ``.dot`` files land in ``docs/source/_static/diagrams/`` and are rendered to
SVG at build time by ``sphinx.ext.graphviz``, so the site never carries a stale
committed image. The visual language — one colour and one shape per category —
lives in :mod:`style`.

The five diagrams are the ones the architecture section is built around:

1. ``lifecycle`` — builder to output nodes, the path a calculation takes.
2. ``provenance`` — the graph a single calculation leaves in the database.
3. ``modules`` — which module imports which, and what each is responsible for.
4. ``io_contract`` — every input port and output node, required or optional.
5. ``ecosystem`` — where the plugin sits among daemon, storage and scheduler.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from style import digraph, edge, legend, node

OUTPUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "source" / "_static" / "diagrams"


def lifecycle() -> str:
    """The path of one calculation, from Python inputs to parsed output nodes."""
    body = [
        '  subgraph cluster_local { label="1. Your machine (or the daemon worker)"; '
        'fontsize="10"; color="#7a8290"; fontcolor="#7a8290"; style="dashed";',
        node("inputs", "inputs\\nparameters, code, skf_files, ...", "DATA"),
        node("submit", "engine.submit()\\nor engine.run()", "INFRA"),
        node("prepare", "DftbPlusCalculation\\n.prepare_for_submission()", "PLUGIN", focus=True),
        node("sandbox", "sandbox folder\\ndftb_in.hsd, mat_files", "FILE"),
        node("calcinfo", "CalcInfo\\nretrieve_list, local_copy_list", "INFRA"),
        "  }",
        '  subgraph cluster_remote { label="2. The compute resource"; fontsize="10"; '
        'color="#7a8290"; fontcolor="#7a8290"; style="dashed";',
        node("workdir", "remote working directory\\ndftb_in.hsd + *.skf", "FILE"),
        node("dftb", "dftb+", "BINARY"),
        node("outfiles", "dftb.out, detailed.out,\\nband.out, geom.out.*, ...", "FILE"),
        "  }",
        '  subgraph cluster_parse { label="3. Back in the database"; fontsize="10"; '
        'color="#7a8290"; fontcolor="#7a8290"; style="dashed";',
        node("retrieved", "retrieved\\n(FolderData)", "DATA"),
        node("parse", "DftbPlusParser.parse()", "PLUGIN", focus=True),
        node("outparams", "output_parameters\\n(Dict)", "DATA"),
        node("exit", "exit code\\n0 / 300 / 310 / 320 / 330", "INFRA"),
        "  }",
        edge("inputs", "submit"),
        edge("submit", "prepare", "engine calls the plugin"),
        edge("prepare", "sandbox", "writes"),
        edge("prepare", "calcinfo", "returns"),
        edge("calcinfo", "workdir", "upload + local_copy_list"),
        edge("sandbox", "workdir", "upload"),
        edge("workdir", "dftb", "scheduler runs"),
        edge("dftb", "outfiles", "stdout to dftb.out"),
        edge("outfiles", "retrieved", "retrieve_list"),
        edge("retrieved", "parse"),
        edge("parse", "outparams", "self.out()"),
        edge("parse", "exit", "return"),
        legend(
            [
                ("DATA", "AiiDA Data node"),
                ("PLUGIN", "plugin code"),
                ("FILE", "file on disk"),
                ("BINARY", "external binary"),
                ("INFRA", "AiiDA machinery"),
            ]
        ),
    ]
    return digraph("Calculation lifecycle", body)


def provenance() -> str:
    """The provenance graph a single DFTB+ calculation leaves behind."""
    body = [
        '  {rank="same"; ' + " ".join(f"n_{i};" for i in range(1, 8)) + "}",
        node("n_1", "InstalledCode\\ndftb+@localhost", "DATA"),
        node("n_2", "DftbParameters\\n(Dict subclass)", "DATA"),
        node("n_3", "FolderData\\nskf_files", "DATA", optional=True),
        node("n_4", "FolderData\\nmat_files", "DATA", optional=True),
        node("n_5", "Dict\\nstructure (metadata)", "DATA", optional=True),
        node("n_6", "Bool\\nuse_remote_skf_path", "DATA"),
        node("n_7", "Bool\\nfix_output_prefix", "DATA"),
        node("calc", "CalcJobNode\\nDftbPlusCalculation\\nexit_status = 0", "PROCESS", focus=True),
        node("out_1", "RemoteData\\nremote_folder", "DATA"),
        node("out_2", "FolderData\\nretrieved", "DATA"),
        node("out_3", "Dict\\noutput_parameters", "DATA"),
        *[edge(f"n_{i}", "calc", "INPUT_CALC") for i in range(1, 8)],
        edge("calc", "out_1", "CREATE"),
        edge("calc", "out_2", "CREATE"),
        edge("calc", "out_3", "CREATE"),
        legend(
            [
                ("DATA", "Data node"),
                ("PROCESS", "process node"),
            ]
        ),
        "  // dashed border = optional input port",
    ]
    return digraph("Provenance graph of one calculation", body, nodesep="0.25")


def modules() -> str:
    """Which module imports which, and what each one owns."""
    body = [
        node("calculations", "calculations.py\\nDftbPlusCalculation\\nHSD generation + staging", "PLUGIN", focus=True),
        node("parsers", "parsers.py\\nDftbPlusParser\\noutput classification", "PLUGIN"),
        node("data", "data/__init__.py\\nDftbParameters\\ntop-level block validation", "PLUGIN"),
        node("cli", "cli.py\\nverdi data dftbplus\\nlist / export / hsd", "PLUGIN"),
        node("helpers", "helpers.py\\nget_computer / get_code\\ntest + example convenience", "PLUGIN"),
        node("aiida", "aiida-core\\nCalcJob, Parser, Dict, ...", "INFRA"),
        node("voluptuous", "voluptuous\\nschema validation", "INFRA"),
        edge("parsers", "calculations", "CalculationFactory('dftbplus')"),
        edge("data", "calculations", "_dict_to_hsd()"),
        edge("cli", "data", "DataFactory('dftbplus')\\nat runtime", style="dashed"),
        edge("data", "voluptuous"),
        edge("calculations", "aiida"),
        edge("parsers", "aiida"),
        edge("helpers", "aiida"),
        edge("cli", "aiida"),
        "  // calculations.py imports nothing from the rest of the package: it is the root.",
    ]
    return digraph("Module dependency map", body, rankdir="LR")


def io_contract() -> str:
    """Every input port and output node, with type and whether it is required."""
    body = [
        '  subgraph cluster_in { label="Inputs"; fontsize="10"; color="#7a8290"; fontcolor="#7a8290"; style="dashed";',
        node("code", "code : InstalledCode\\nrequired", "DATA"),
        node("parameters", "parameters : Dict\\nexactly one of these two", "DATA", optional=True),
        node("dftb_input", "dftb_input : SinglefileData\\nexactly one of these two", "DATA", optional=True),
        node("skf", "skf_files : FolderData\\noptional", "DATA", optional=True),
        node("mat", "mat_files : FolderData\\noptional", "DATA", optional=True),
        node("structure", "structure : Dict\\noptional, provenance only", "DATA", optional=True),
        node("remote_flag", "use_remote_skf_path : Bool\\ndefault False", "DATA"),
        node("prefix_flag", "fix_output_prefix : Bool\\ndefault True", "DATA"),
        node("metadata", "metadata.options\\nresources, walltime, parser_name", "INFRA"),
        "  }",
        node("calc", "DftbPlusCalculation", "PROCESS", focus=True),
        '  subgraph cluster_out { label="Outputs"; fontsize="10"; color="#7a8290"; '
        'fontcolor="#7a8290"; style="dashed";',
        node("remote_folder", "remote_folder : RemoteData\\nalways", "DATA"),
        node("retrieved", "retrieved : FolderData\\nalways", "DATA"),
        node("output_parameters", "output_parameters : Dict\\nonly on exit code 0", "DATA", optional=True),
        "  }",
        edge("code", "calc"),
        edge("parameters", "calc", "or"),
        edge("dftb_input", "calc"),
        edge("skf", "calc"),
        edge("mat", "calc"),
        edge("structure", "calc"),
        edge("remote_flag", "calc"),
        edge("prefix_flag", "calc"),
        edge("metadata", "calc"),
        edge("calc", "remote_folder"),
        edge("calc", "retrieved"),
        edge("calc", "output_parameters"),
        "  // dashed border = optional",
    ]
    return digraph("Input/output node contract", body, rankdir="LR", nodesep="0.2")


def ecosystem() -> str:
    """Where the plugin sits among AiiDA's moving parts."""
    body = [
        node("user", "your script\\nor verdi", "INFRA"),
        node("engine", "AiiDA engine\\n(daemon worker)", "INFRA"),
        node("plugin", "aiida-dftbplus\\nCalcJob + Parser", "PLUGIN", focus=True),
        node("storage", "storage backend\\nPostgreSQL or sqlite\\n+ file repository", "INFRA"),
        node("transport", "transport\\ncore.local / core.ssh", "INFRA"),
        node("scheduler", "scheduler\\ncore.direct / slurm / pbspro", "INFRA"),
        node("computer", "Computer\\nlocalhost or HPC", "INFRA"),
        node("dftb", "dftb+", "BINARY"),
        node("skf", "Slater-Koster files\\n*.skf", "FILE"),
        edge("user", "engine", "submit()"),
        edge("engine", "plugin", "entry points\\naiida.calculations / aiida.parsers"),
        edge("engine", "storage", "nodes + provenance"),
        edge("engine", "transport"),
        edge("transport", "computer", "copy files"),
        edge("engine", "scheduler", "queue the job"),
        edge("scheduler", "computer"),
        edge("computer", "dftb", "runs"),
        edge("skf", "dftb", "read by", style="dashed"),
        legend(
            [
                ("PLUGIN", "this package"),
                ("INFRA", "AiiDA machinery"),
                ("BINARY", "external binary"),
                ("FILE", "files you supply"),
            ]
        ),
    ]
    return digraph("aiida-dftbplus in the AiiDA ecosystem", body, rankdir="LR")


DIAGRAMS = {
    "lifecycle": lifecycle,
    "provenance": provenance,
    "modules": modules,
    "io_contract": io_contract,
    "ecosystem": ecosystem,
}


def main() -> int:
    """Write every diagram to ``docs/source/_static/diagrams``."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, builder in DIAGRAMS.items():
        target = OUTPUT_DIR / f"{name}.dot"
        target.write_text(builder(), encoding="utf8")
        print(f"wrote {target.relative_to(OUTPUT_DIR.parents[3])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
