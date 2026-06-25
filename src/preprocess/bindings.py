"""Build a C++ -> PyChrono binding map from the SWIG interface files.

PyChrono is a SWIG binding; the `.i` files under src/chrono_swig/interface/<module>/
declare which C++ headers are exposed to Python and under which module. Parsing
them lets us tag C++ chunks with `python_exposed` + `pychrono_module` so the
retriever knows a class is reachable from Python (and where), without installing
PyChrono.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, Set

_INCLUDE_RE = re.compile(r'%include\s+"([^"]+\.h[px]{0,2})"')

# interface subdir -> pychrono module name (core is the base `pychrono`/`chrono`)
_MODULE_NAME = {
    "core": "pychrono",
    "fea": "pychrono.fea",
    "vehicle": "pychrono.vehicle",
    "sensor": "pychrono.sensor",
    "irrlicht": "pychrono.irrlicht",
    "postprocess": "pychrono.postprocess",
    "robot": "pychrono.robot",
    "ros": "pychrono.ros",
    "cascade": "pychrono.cascade",
    "fsi": "pychrono.fsi",
    "parsers": "pychrono.parsers",
    "pardisomkl": "pychrono.pardisomkl",
    "vsg": "pychrono.vsg",
}


@dataclass
class BindingMap:
    header_to_module: Dict[str, str] = field(default_factory=dict)  # header basename -> module
    exposed_headers: Set[str] = field(default_factory=set)          # header basenames
    exposed_symbols: Dict[str, str] = field(default_factory=dict)   # ClassName -> module

    def lookup(self, path: str):
        """Return (python_exposed, pychrono_module) for a C++ file path."""
        base = os.path.basename(path)
        if base in self.exposed_headers:
            return True, self.header_to_module.get(base, "")
        return False, ""


def build_binding_map(repo: str) -> BindingMap:
    bm = BindingMap()
    iface_root = os.path.join(repo, "src", "chrono_swig", "interface")
    if not os.path.isdir(iface_root):
        return bm

    for dirpath, _dirnames, filenames in os.walk(iface_root):
        # module = first path component under interface/
        rel = os.path.relpath(dirpath, iface_root).replace("\\", "/")
        module_key = rel.split("/")[0] if rel != "." else ""
        module = _MODULE_NAME.get(module_key, "pychrono")

        for fn in filenames:
            if not fn.endswith(".i"):
                continue
            # The interface file is conventionally named after the class it wraps.
            stem = os.path.splitext(fn)[0]
            if stem.startswith("Ch"):
                bm.exposed_symbols.setdefault(stem, module)
            fpath = os.path.join(dirpath, fn)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            except OSError:
                continue
            for m in _INCLUDE_RE.finditer(text):
                header_base = os.path.basename(m.group(1))
                bm.exposed_headers.add(header_base)
                bm.header_to_module.setdefault(header_base, module)
    return bm
