r"""PyChrono 9.0 -> 10.0 migration porter (build-time aid for the examples set).

Codifies the mechanical find/replace rules from the 9.0->10.0 migration guide and
applies them to example scripts. Structural changes that cannot be done safely by
substitution (e.g. the ChInteractiveDriver argument change, SetOutput's new Mode
arg, the ChCameraSensor ctor) are applied where mechanical and otherwise FLAGGED
for review. Verification (running on PyChrono 10.0) is the real gate, this just
does the safe bulk of the edit.

Usage:
  python src/preprocess/migrate.py <src_dir> <dst_dir>
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Tuple

# (regex, replacement, description) - safe, context-free token substitutions.
_SUBS: List[Tuple[re.Pattern, str, str]] = [
    (re.compile(r"\bveh\.VisualizationType_(NONE|PRIMITIVES|MESH|COLLISION|MODEL_FILE)\b"),
     r"chrono.VisualizationType_\1", "VisualizationType moved veh-> chrono"),
    (re.compile(r"\bveh\.GetDataFile\("), "veh.GetVehicleDataFile(", "GetDataFile -> GetVehicleDataFile"),
    (re.compile(r"\.SetSymbolscale\("), ".SetSymbolScale(", "SetSymbolscale -> SetSymbolScale"),
    (re.compile(r"\.SetPlane\("), ".SetReferenceFrame(", "SCMTerrain SetPlane -> SetReferenceFrame"),
    (re.compile(r"logo_pychrono_alpha\.png"), "logo_chrono_alpha.png", "logo asset renamed"),
    (re.compile(r"\bveh\.ChVehicleOutput\.ASCII\b"), "chrono.ChOutput.Type_ASCII", "ChVehicleOutput.ASCII -> ChOutput.Type_ASCII"),
    (re.compile(r"\bveh\.ChInteractiveDriverIRR\b"), "veh.ChInteractiveDriver", "ChInteractiveDriverIRR -> ChInteractiveDriver"),
    (re.compile(r"\bveh\.ChSuspensionTestRigInteractiveDriverIRR\b"), "veh.ChSuspensionTestRigInteractiveDriver", "STR interactive driver de-Irrlicht"),
    # Irrlicht drawing helpers were PascalCased in 10.0 (and COG -> COM). Names
    # confirmed by the 10.0 runtime's "did you mean" errors during verification.
    (re.compile(r"\bdrawAllCOGs\b"), "DrawAllCOMs", "drawAllCOGs -> DrawAllCOMs"),
    (re.compile(r"\bdrawAllLinkframes\b"), "DrawAllLinkframes", "drawAllLinkframes -> DrawAllLinkframes"),
    (re.compile(r"\bdrawAllBoundingBoxes\b"), "DrawAllBoundingBoxes", "drawAllBoundingBoxes -> DrawAllBoundingBoxes"),
    (re.compile(r"\bdrawSegment\b"), "DrawSegment", "drawSegment -> DrawSegment"),
    (re.compile(r"\bdrawGrid\b"), "DrawGrid", "drawGrid -> DrawGrid"),
    (re.compile(r"\bdrawCircle\b"), "DrawCircle", "drawCircle -> DrawCircle"),
    (re.compile(r"\bdrawPolyline\b"), "DrawPolyline", "drawPolyline -> DrawPolyline"),
    (re.compile(r"\bdrawSpring\b"), "DrawSpring", "drawSpring -> DrawSpring"),
    (re.compile(r"\bdrawRotSpring\b"), "DrawRotSpring", "drawRotSpring -> DrawRotSpring"),
    (re.compile(r"\bdrawCoordsys\b"), "DrawCoordsys", "drawCoordsys -> DrawCoordsys"),
    (re.compile(r"\bdrawChFunction\b"), "DrawChFunction", "drawChFunction -> DrawChFunction"),
    (re.compile(r"\bdrawProfiler\b"), "DrawProfiler", "drawProfiler -> DrawProfiler"),
    (re.compile(r"\bEmptyAccumulators\b"), "EmptyAccumulator", "EmptyAccumulators -> EmptyAccumulator"),
    (re.compile(r"\bsens\.PINHOLE\b"), "sens.CameraLensModelType_PINHOLE", "sensor PINHOLE -> CameraLensModelType_PINHOLE"),
    (re.compile(r"\.SetModifiedNewton\(\s*True\s*\)"),
     ".SetJacobianUpdateMethod(chrono.ChTimestepperImplicit.JacobianUpdate_EVERY_STEP)", "SetModifiedNewton(True)"),
    (re.compile(r"\.SetModifiedNewton\(\s*False\s*\)"),
     ".SetJacobianUpdateMethod(chrono.ChTimestepperImplicit.JacobianUpdate_EVERY_ITERATION)", "SetModifiedNewton(False)"),
]

# Whole-line deletions (the vehicle data path is auto-set in 10.0).
_LINE_DELETE = [
    re.compile(r"^\s*veh\.SetDataPath\(\s*chrono\.GetChronoDataPath\(\)\s*\+\s*['\"]vehicle/['\"]\s*\)\s*$"),
]

# Patterns that, if present after porting, need a human/agent look (structural).
_FLAGS = [
    (re.compile(r"\bChInteractiveDriver\b"), "ChInteractiveDriver: arg must be the vehicle (e.g. model.GetVehicle()), not the visual system; add vis.AttachDriver(driver)"),
    (re.compile(r"\.SetOutput\("), "SetOutput: a Mode argument was inserted (chrono.ChOutput.Mode_FRAMES)"),
    (re.compile(r"\bChCameraSensor\("), "ChCameraSensor: ctor params changed; pass gamma/use_fog by keyword, new use_denoiser/integrator args"),
    (re.compile(r"\bChVisualShapeFEA\b"), "ChVisualShapeFEA was removed in 10.0; FEA mesh visualization is now done differently (VisualizationCallback) - needs a manual rewrite"),
    (re.compile(r"\bChLoaderGravity\b"), "ChLoaderGravity was removed in 10.0; apply gravity via mesh.SetAutomaticGravity()/system gravity - needs a manual rewrite"),
]

# Leftover 9.0 symbols that should NOT survive a correct port (the guide's grep).
_LEFTOVER = re.compile(
    r"ChInteractiveDriverIRR|veh\.GetDataFile|veh\.SetDataPath|\.SetSymbolscale|"
    r"veh\.VisualizationType_|ChVehicleOutput|SetModifiedNewton|logo_pychrono_alpha"
)


@dataclass
class FileReport:
    path: str
    changes: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    leftover_9_0: bool = False


def migrate_text(text: str) -> Tuple[str, FileReport]:
    rep = FileReport(path="")
    lines = text.split("\n")
    kept = []
    for ln in lines:
        if any(p.match(ln) for p in _LINE_DELETE):
            rep.changes.append("deleted veh.SetDataPath(...vehicle/) line")
            continue
        kept.append(ln)
    text = "\n".join(kept)

    for pat, repl, desc in _SUBS:
        text, n = pat.subn(repl, text)
        if n:
            rep.changes.append(f"{desc} ({n})")

    for pat, msg in _FLAGS:
        if pat.search(text):
            rep.flags.append(msg)

    rep.leftover_9_0 = bool(_LEFTOVER.search(text))
    return text, rep


def migrate_tree(src_dir: str, dst_dir: str) -> List[FileReport]:
    reports: List[FileReport] = []
    for dirpath, _dn, filenames in os.walk(src_dir):
        if os.sep + ".git" in dirpath:
            continue
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            sp = os.path.join(dirpath, fn)
            rel = os.path.relpath(sp, src_dir)
            with open(sp, "r", encoding="utf-8", errors="ignore") as fh:
                new_text, rep = migrate_text(fh.read())
            rep.path = rel.replace("\\", "/")
            dp = os.path.join(dst_dir, rel)
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            with open(dp, "w", encoding="utf-8") as fh:
                fh.write(new_text)
            reports.append(rep)
    return reports


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: migrate.py <src_dir> <dst_dir>", file=sys.stderr)
        raise SystemExit(2)
    src, dst = sys.argv[1], sys.argv[2]
    reports = migrate_tree(src, dst)
    changed = sum(1 for r in reports if r.changes)
    flagged = sum(1 for r in reports if r.flags)
    leftover = sum(1 for r in reports if r.leftover_9_0)
    print(f"ported {len(reports)} files -> {dst}")
    print(f"  changed: {changed}   flagged-for-review: {flagged}   leftover-9.0-symbols: {leftover}")
    with open(os.path.join(dst, "_migration_report.json"), "w", encoding="utf-8") as fh:
        json.dump([r.__dict__ for r in reports], fh, indent=2)
    print(f"  report: {os.path.join(dst, '_migration_report.json')}")


if __name__ == "__main__":
    main()
