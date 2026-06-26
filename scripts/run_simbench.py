#!/usr/bin/env python3
"""
Generate SimBench responses for benchmarking baseline vs RAG models.

Produces first/second/third_response.txt + .py + _cleaned.py for each
system under SimBench/output_llms/<folder>/<system>/.

Usage:
    python scripts/run_simbench.py --model gpt-4o-mini
    python scripts/run_simbench.py --model gpt-4o-mini --rag
    python scripts/run_simbench.py --model claude-opus-4-8
    python scripts/run_simbench.py --model claude-opus-4-8 --rag

    # Run only a subset of systems for quick testing:
    python scripts/run_simbench.py --model gpt-4o-mini --rag --systems pendulum beam
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from inference.llm import LLM
from inference.vector_search import retrieve, _SYSTEM_PROMPT, _VERSION_DIFF_PROMPT

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SIMBENCH = ROOT / "SimBench"
DEMO_DATA = SIMBENCH / "demo_data"
OUTPUT_DIR = SIMBENCH / "output_llms"

# (txt_file, pyinput_file, label)
# pyinput_file is the expert-provided starter code for turns 2 & 3,
# matching the scoring-script methodology in gpt/claude_generate_simulation.py.
TURNS = [
    ("input1.txt", None,          "first"),
    ("input2.txt", "pyinput2.py", "second"),
    ("input3.txt", "pyinput3.py", "third"),
]

_TURN23_USER_TEMPLATE = """\
Here is the PyChrono code you need to modify:
{code}

Please modify the given code based on the following instructions:
{prompt}

To complete the task, follow these steps:

Review the given PyChrono script and identify any errors, including syntax errors, logical errors, incorrect method names, and parameter issues.
Correct the identified errors in the script to ensure it runs correctly.
Modify the script based on the provided instructions to ensure it meets the specified requirements.

Provide the corrected and modified script below:\
"""

ALL_SYSTEMS = [
    "art", "beam", "buckling", "cable", "camera", "citybus", "curiosity",
    "feda", "gator", "gear", "gps_imu", "handler", "hmmwv", "kraz", "lidar",
    "m113", "man", "mass_spring_damper", "particles", "pendulum",
    "rigid_highway", "rigid_multipatches", "rotor", "scm", "scm_hill",
    "sedan", "sensros", "slider_crank", "tablecloth", "turtlebot",
    "uazbus", "veh_app", "vehros", "viper",
]

_BASELINE_SYSTEM = f"""You are an expert in Chrono and PyChrono, the physics-based simulation libraries.
Generate complete, correct PyChrono code that is compatible with version 10.0.0.
Return the full script inside a single ```python ... ``` block with no other code blocks.

{_VERSION_DIFF_PROMPT}"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_python(text: str) -> str:
    """Extract code from ```python ... ``` blocks; fall back to raw text."""
    blocks = re.findall(r"```python(.*?)```", text, re.DOTALL)
    if blocks:
        return "\n\n".join(b.strip() for b in blocks)
    # single opening fence with no closing
    m = re.search(r"```python(.*)", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _remove_comments(code: str) -> str:
    code = re.sub(r"#.*", "", code)
    code = re.sub(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', "", code)
    return code.strip()


def _save(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_system(system: str, model: str, use_rag: bool) -> None:
    system_dir = DEMO_DATA / system
    if not system_dir.exists():
        print(f"  [skip] {system}: not found in demo_data")
        return

    folder = f"{model}-rag" if use_rag else model
    out_dir = OUTPUT_DIR / folder / system

    llm = LLM(model=model)

    # RAG context is fetched once using the turn-1 query, matching the
    # scoring-script methodology (context injected into system prompt).
    if use_rag:
        turn1_query = (system_dir / "input1.txt").read_text(encoding="utf-8").strip()
        context = retrieve(turn1_query)
        system_prompt = f"{_SYSTEM_PROMPT}\n\nretrieved_data:\n{context}"
    else:
        system_prompt = _BASELINE_SYSTEM

    for in_file, pyinput_file, label in TURNS:
        query = (system_dir / in_file).read_text(encoding="utf-8").strip()

        # Pseudo multi-turn: each call is standalone (no history).
        # Turns 2 & 3 build on the expert-provided pyinput starter code,
        # not the model's own prior output — matching gpt/claude_generate_simulation.py.
        if pyinput_file is None:
            user_message = query
        else:
            pyinput_path = system_dir / pyinput_file
            if not pyinput_path.exists():
                print(f"    [{label}] warning: {pyinput_file} not found, falling back to plain prompt")
                user_message = query
            else:
                expert_code = pyinput_path.read_text(encoding="utf-8").strip()
                user_message = _TURN23_USER_TEMPLATE.format(code=expert_code, prompt=query)

        response = llm.complete(system=system_prompt, user=user_message)

        # Persist all three file variants expected by scoring scripts
        _save(out_dir / f"{label}_response.txt", response)

        py_code = _extract_python(response)
        _save(out_dir / f"{label}_response.py", py_code)
        _save(out_dir / f"{label}_cleaned_response.py", _remove_comments(py_code))

        print(f"    [{label}] saved")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run SimBench generation for a model.")
    parser.add_argument(
        "--model",
        choices=LLM.SUPPORTED_MODELS,
        default=LLM.ANTHROPIC_MODEL,
        help="Model to benchmark (default: claude-opus-4-8)",
    )
    parser.add_argument(
        "--rag",
        action="store_true",
        help="Inject RAG context from the vector store on turn 1",
    )
    parser.add_argument(
        "--systems",
        nargs="+",
        metavar="SYSTEM",
        default=ALL_SYSTEMS,
        help="Subset of systems to run (default: all 34)",
    )
    args = parser.parse_args()

    folder = f"{args.model}-rag" if args.rag else args.model
    print(f"Model  : {args.model}")
    print(f"RAG    : {args.rag}")
    print(f"Output : SimBench/output_llms/{folder}/")
    print(f"Systems: {len(args.systems)}")
    print()

    for i, system in enumerate(args.systems, 1):
        print(f"[{i}/{len(args.systems)}] {system}")
        try:
            run_system(system, args.model, args.rag)
        except Exception as exc:
            print(f"  [ERROR] {exc}")
        print()


if __name__ == "__main__":
    main()
