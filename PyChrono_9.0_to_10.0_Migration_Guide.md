# PyChrono 9.0.0 → 10.0.0 Migration Guide

> **Purpose.** This document enumerates the concrete API differences that affect
> *PyChrono* simulation code when upgrading from release **9.0.0** to release
> **10.0.0**. It is written to be consumed by an automated agent: every breaking
> change is given as a precise *before → after* rule with a regex/search hint and a
> code example. Apply the **Breaking Changes** section mechanically; the
> **Non‑Breaking / Optional** and **Removed Modules** sections are informational.

**Source of truth.** Derived from a direct diff of git tags `9.0.0` and `10.0.0`
in this repository (Python demos under `src/demos/python/`, SWIG interface files
under `src/chrono_swig/`, and the affected C++ headers) plus the `Release 10.0.0`
section of `CHANGELOG.md`.

---

## How to apply (agent procedure)

1. Run the **mechanical find/replace** rules in the table below in order. They are
   safe, context‑free token substitutions.
2. Apply the **structural changes** (interactive driver, output system, camera
   constructor) which require multi-line edits — match on the *pattern*, not just a
   token.
3. Re-check **removed modules**; if any imported, the code cannot run on 10.0 as-is.
4. Verify with the steps in the final section.

---

## 1. Quick‑reference find/replace table (mechanical, context‑free)

| # | 9.0.0 (find)                                   | 10.0.0 (replace)                                  | Scope / Notes |
|---|------------------------------------------------|---------------------------------------------------|---------------|
| 1 | `veh.VisualizationType_<X>`                    | `chrono.VisualizationType_<X>`                    | Enum moved from the `vehicle` module to `core`. All suffixes: `_NONE`, `_PRIMITIVES`, `_MESH`, `_COLLISION`, `_MODEL_FILE`. **`veh.CollisionType_*` did NOT move — leave it as `veh.`** |
| 2 | `veh.GetDataFile(`                             | `veh.GetVehicleDataFile(`                         | Vehicle-module data-file accessor renamed. |
| 3 | `veh.SetDataPath(chrono.GetChronoDataPath() + 'vehicle/')` | *(delete the line)*                   | Vehicle data path is now set automatically. Remove the call entirely. |
| 4 | `.SetSymbolscale(`                             | `.SetSymbolScale(`                                | Capitalization fix on visual-system method. |
| 5 | `.SetPlane(`  (on an `SCMTerrain` object)      | `.SetReferenceFrame(`                             | `SCMTerrain::SetPlane` → `SetReferenceFrame`. Same `ChCoordsysd` argument. |
| 6 | `GetChronoDataFile('logo_pychrono_alpha.png')` | `GetChronoDataFile('logo_chrono_alpha.png')`      | Data asset renamed (old file no longer shipped). Also matches double-quoted form. |
| 7 | `veh.ChVehicleOutput.ASCII`                    | `chrono.ChOutput.Type_ASCII`                      | See §3 (output system) — the surrounding `SetOutput` call also changes. |

> Rule 1 caution: only rewrite the `veh.VisualizationType_*` *symbol reference*. Method
> names like `SetChassisVisualizationType(...)` are unchanged — only their **argument**
> moves from `veh.` to `chrono.`.

---

## 2. Interactive driver refactor (Chrono::Vehicle)

The Irrlicht-specific interactive driver class **`ChInteractiveDriverIRR` was removed**.
The interactive driver is now constructed from the *vehicle* (not the visual system)
and is attached to the visual system separately.

**Before (9.0.0):**
```python
driver = veh.ChInteractiveDriverIRR(vis)
driver.SetSteeringDelta(render_step_size / steering_time)
driver.SetThrottleDelta(render_step_size / throttle_time)
driver.SetBrakingDelta(render_step_size / braking_time)
driver.Initialize()
```

**After (10.0.0):**
```python
driver = veh.ChInteractiveDriver(hmmwv.GetVehicle())   # pass the ChVehicle
driver.SetSteeringDelta(render_step_size / steering_time)
driver.SetThrottleDelta(render_step_size / throttle_time)
driver.SetBrakingDelta(render_step_size / braking_time)
driver.Initialize()
...
vis.AttachVehicle(hmmwv.GetVehicle())
vis.AttachDriver(driver)        # NEW: register the driver with the visual system
```

**Agent rule:**
- Replace `veh.ChInteractiveDriverIRR(<vis>)` → `veh.ChInteractiveDriver(<vehicle>)`.
  The argument changes from the visualization object to the `ChVehicle`
  (commonly `<model>.GetVehicle()`, or the `vehicle` object for JSON-built vehicles).
- After the `vis.AttachVehicle(...)` call, add `vis.AttachDriver(driver)`.

The suspension-test-rig interactive driver was likewise de-Irrlicht-ized
(`ChSuspensionTestRigInteractiveDriverIRR` → `ChSuspensionTestRigInteractiveDriver`).

---

## 3. Simulation output & checkpointing system overhaul

The output API was unified under the new core `ChOutput` type, and a global
output-path facility was added.

### 3a. Vehicle `SetOutput` signature
A **`Mode` argument was inserted** and the type enum moved to the core module.

**Before:**
```python
hmmwv.GetVehicle().SetOutput(veh.ChVehicleOutput.ASCII, out_dir, "output", 0.1)
```
**After:**
```python
hmmwv.GetVehicle().SetOutput(chrono.ChOutput.Type_ASCII,
                             chrono.ChOutput.Mode_FRAMES,
                             out_dir, "output", 0.1)
```
**Agent rule:** `SetOutput(veh.ChVehicleOutput.ASCII, A, B, C)` →
`SetOutput(chrono.ChOutput.Type_ASCII, chrono.ChOutput.Mode_FRAMES, A, B, C)`.
(Output type enumerators are now `chrono.ChOutput.Type_ASCII`, `chrono.ChOutput.Type_HDF5`.)

### 3b. New global output-path helpers
10.0.0 demos centralize output directories via:
```python
chrono.SetChronoOutputPath("../DEMO_OUTPUT/")
out_dir = chrono.GetChronoOutputPath() + "HMMWV/"
```
This is **optional** for migration (hand-rolled paths still work), but it is the
new idiom. If converting, replace ad-hoc `out_dir = "SENSOR_OUTPUT/"` style strings
with the helpers above.

---

## 4. Sensor camera constructor change (Chrono::Sensor)

`ChCameraSensor`’s constructor parameter list changed. Positional callers will break.

**9.0.0 signature:**
```
ChCameraSensor(parent, updateRate, offsetPose, w, h, hFOV,
               supersample_factor=1, lens_model=PINHOLE,
               use_gi=False, gamma=2.2, use_fog=True)
```
**10.0.0 signature:**
```
ChCameraSensor(parent, updateRate, offsetPose, w, h, hFOV,
               supersample_factor=1, lens_model=PINHOLE,
               use_diffuse_reflect=False, use_denoiser=False,
               integrator=sens.Integrator_LEGACY,   # NEW
               gamma=2.2, use_fog=False)             # use_fog default flipped to False
```
**Agent rules:**
- The old 9th positional argument `use_gi` (bool) is gone; the nearest equivalent is
  `use_diffuse_reflect` (bool, same position). Keep the boolean value.
- Two new parameters (`use_denoiser`, `integrator`) are inserted **before** `gamma`.
  Any code passing `gamma`/`use_fog` *positionally* must be updated (or switched to
  keyword arguments — recommended).
- Choose rendering algorithm via `sens.Integrator_LEGACY` (old behavior) or the new
  `sens.Integrator_PATH`.
- Note the default of `use_fog` changed `True → False`.

New, additive sensor capabilities in 10.0 (no migration needed unless adopting):
`ChPhysCameraSensor`, `ChNormalCamera`, multiple light types, depth/normal/segmentation
filters and `GetMostRecentDepthBuffer()` etc. The old `TensorRT` feature was removed.

---

## 5. Implicit integrator / HHT: "modified Newton" → Jacobian update enum

`ChTimestepperHHT::SetModifiedNewton(bool)` was **removed**. Jacobian update strategy
is now an enum on the implicit-timestepper base class.

**Before:**
```python
integrator.SetModifiedNewton(True)    # reuse Jacobian for all iterations of a step
integrator.SetModifiedNewton(False)   # full Newton
```
**After:**
```python
integrator.SetJacobianUpdateMethod(chrono.ChTimestepperImplicit.JacobianUpdate_EVERY_STEP)       # was True
integrator.SetJacobianUpdateMethod(chrono.ChTimestepperImplicit.JacobianUpdate_EVERY_ITERATION)  # was False
# also available: JacobianUpdate_NEVER, JacobianUpdate_AUTOMATIC
```
Equivalence map: `SetModifiedNewton(True)` → `EVERY_STEP`; `SetModifiedNewton(False)`
→ `EVERY_ITERATION`. Default is `EVERY_STEP`.

Also: `SetTimestepper(...)` now has overloads for each implicit stepper type; the
recommended idiom is `sys.SetTimestepperType(...)` followed by retrieving/casting the
timestepper, rather than constructing one and passing it in.

---

## 6. Non‑breaking / optional additions

These do **not** break 9.0 code but appear throughout the 10.0 demos and are the new
preferred style:

- **Gravity convenience setters.** `sys.SetGravityX()`, `sys.SetGravityY()`,
  `sys.SetGravityZ()` set ±9.8 m/s² on an axis. The default gravity is `[0,0,0]` in
  **both** versions — adding `sys.SetGravityY()` is a convenience, not a correctness
  fix. (Existing `SetGravitationalAcceleration(ChVector3d(...))` still works.)
- **`SetChronoDataPath(...)` comment blocks** were removed from demos (the path is
  auto-set). No code action required; safe to drop the commented hint lines.
- **PyChrono–NumPy integration** (when built with NumPy): `to_numpy()` and
  `__array__` on `ChVector3d`, `ChQuaterniond`, `ChMatrix33d`, `ChMatrixDynamicd`,
  `ChMatrix66d`; `np.asarray(obj)` works directly; new SPH/FSI getters return NumPy
  arrays. Sensor data getters `Get*Data()` are available only when NumPy is present.
- **Newly wrapped modules in PyChrono:** Chrono::VSG (`pychrono.vsg`) and
  Chrono::FSI‑SPH. New vehicle wrappers: `ChTireTestRig`, and SCMTerrain
  `GetModifiedNodes`/`SetModifiedNodes`. PyChrono now supports multithreading and
  co-simulation callbacks (e.g. FSI‑SPH ↔ MBS).
- **YAML parsers** (Chrono::Parsers) for models/simulations are new and additive.

---

## 7. Removed modules / features (10.0.0)

If 9.0 code depends on any of these, it must be rewritten — there is no drop-in
replacement except where noted:

- **Chrono::Distributed** (MPI domain-decomposition for Multicore granular) — removed.
- **Chrono::Pardiso** (Pardiso-project solver) — removed. **Use Chrono::PardisoMKL
  (`pychrono.pardisomkl`), which remains available.**
- **Chrono::OpenGL** run-time visualization — removed. **Use Chrono::VSG
  (`pychrono.vsg`) instead.**
- **MPM solver** in Chrono::Multicore — removed.
- **Custom optimization solvers** in core Chrono — removed.
- **SPH support in core Chrono** — removed (use the Chrono::FSI‑SPH fluid solver).
- **Sensor `TensorRT`** feature — removed (transfer data via Chrono::ROS or PyChrono).

> None of these were exposed as dedicated importable PyChrono modules in 9.0, so the
> typical failure mode is a missing symbol/feature rather than a failed `import`.

### Packaging note
Conda packages for PyChrono 10.0 target **Python 3.12 and 3.13** and **do not
include Chrono::Cascade** (SWIG/`pythonocc-core` incompatibility). To use
Chrono::Cascade or another Python version, build PyChrono from source.

---

## 8. Module / API change index by area

| Area (PyChrono module)        | Change | Section |
|-------------------------------|--------|---------|
| `pychrono.core`               | `VisualizationType_*` now lives here; `SetGravityX/Y/Z`; `ChOutput`, `Set/GetChronoOutputPath`; `ChTimestepperImplicit.JacobianUpdate`; NumPy helpers | §1, §3, §5, §6 |
| `pychrono.vehicle`            | `GetVehicleDataFile`; `SetDataPath` removed; `ChInteractiveDriver` replaces `ChInteractiveDriverIRR`; `SetOutput` Mode arg; `SCMTerrain.SetReferenceFrame`; `SetSymbolScale`; new `ChTireTestRig` | §1, §2, §3 |
| `pychrono.sensor`             | `ChCameraSensor` ctor params; `Integrator_LEGACY/PATH`; new physical camera/normal camera/lights; `Get*Data()` gated on NumPy; TensorRT removed | §4, §7 |
| `pychrono.irrlicht`/vehicle vis | `ChInteractiveDriverIRR` removed; `AttachDriver`; `SetSymbolScale` | §1, §2 |
| `pychrono.vsg` (NEW)          | Newly wrapped run-time visualization module | §6 |
| `pychrono.postprocess`        | POV-Ray exporter uses `Set/GetChronoOutputPath` idiom (API otherwise stable) | §3 |
| Removed                       | Distributed, Pardiso (→PardisoMKL), OpenGL (→VSG), Multicore MPM, core SPH/optimizers | §7 |

---

## 9. Verification

After applying the changes, validate against a real PyChrono 10.0 install:

1. **Import check** — confirm modules resolve and no removed module is imported:
   ```bash
   python -c "import pychrono.core, pychrono.vehicle, pychrono.sensor"
   ```
2. **Static grep for leftover 9.0 symbols** (should return nothing):
   ```bash
   grep -rnE "ChInteractiveDriverIRR|veh\.GetDataFile|veh\.SetDataPath|\.SetSymbolscale|\.SetPlane\(|veh\.VisualizationType_|ChVehicleOutput|SetModifiedNewton|logo_pychrono_alpha" <your_code_dir>
   ```
3. **Run a converted script** end-to-end (headless if no display) and confirm it
   advances the simulation loop without `AttributeError`/`TypeError`. Compare against
   the equivalent updated demo under `src/demos/python/` for the same module
   (e.g. `mbs/`, `vehicle/`, `sensor/`) as a reference of correct 10.0 usage.
4. **Numeric sanity** — for converted vehicle/MBS scripts, check gravity is set as
   intended (default is now explicitly documented as `[0,0,0]`; add `SetGravityY()`
   or `SetGravitationalAcceleration(...)` if the original relied on a non-zero value).

---

## Appendix: representative demos to use as 10.0 reference

| Pattern | Reference demo (10.0.0) |
|---------|--------------------------|
| MBS + Irrlicht basics, gravity setter | `src/demos/python/mbs/demo_MBS_revolute.py` |
| Vehicle + interactive driver + output system | `src/demos/python/vehicle/demo_VEH_HMMWV.py` |
| SCM deformable terrain (`SetReferenceFrame`) | `src/demos/python/vehicle/demo_VEH_DeformableSoil.py` |
| Sensor camera (Integrator, new filters) | `src/demos/python/sensor/demo_SEN_camera.py` |
| POV-Ray postprocess + output path | `src/demos/python/postprocess/demo_POST_povray1.py` |
| New modules / features | `demo_VEH_TireTestRig.py`, `demo_VEH_CRMTerrain_WheeledVehicle.py`, `vsg/demo_VSG_vehicles.py`, `yaml/demo_YAML_mbs.py` |
