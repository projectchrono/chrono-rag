# Chrono architecture digest

A curated orientation map of Project Chrono / PyChrono 10.0, served by the `chrono_digest`
MCP tool (call it with no argument to list these headings, or with a heading substring to get
one section). For exact code, use `search_chrono` instead. Scope: Chrono 10.0.

## Core (chrono / pychrono.core)

The base module every simulation uses. Key pieces:

- `ChSystem` variants: `ChSystemNSC` (non-smooth, complementarity contact) and `ChSystemSMC`
  (smooth, penalty contact). Pick one per simulation; it owns bodies, links, and the solver.
- `ChBody` / `ChBodyEasy*`: rigid bodies (mass, inertia, collision, visual assets).
  `ChBodyEasyBox`, `ChBodyEasySphere`, etc. build body + geometry + collision in one call.
- Links and motors: `ChLink*` joints (revolute, prismatic, spherical, ...), `ChLinkMotor*`
  (rotation/linear, position/speed/torque-driven), `ChLinkTSDA` (spring-damper).
- Math types (10.0 naming): `ChVector3d`, `ChQuaterniond`, `ChFramed`, `ChCoordsysd`.
  Gravity: `system.SetGravitationalAcceleration(ChVector3d(0, 0, -9.81))`.
- Collision: a collision system must be selected (`SetCollisionSystemType`, e.g. BULLET);
  materials are `ChContactMaterialNSC` / `ChContactMaterialSMC`.
- Time stepping: `system.DoStepDynamics(dt)` in a loop; solvers and timesteppers are
  configurable (`SetSolverType`, `SetTimestepperType`).

## FEA (chrono/fea / pychrono.fea)

Finite-element structures coupled with multibody dynamics: `ChMesh` plus node/element types
(ANCF cable/shell/brick, Euler-Bernoulli beams, IGA beams, BST shells), `ChLinkNodeFrame`-style
constraints tie meshes to bodies. Static (`DoStaticLinear`/`DoStaticNonlinear`) and dynamic
analyses.

## Vehicle (chrono_vehicle / pychrono.vehicle)

Ground-vehicle modeling: wheeled and tracked templates (suspension, steering, driveline, tire
models incl. Pacejka/TMeasy/rigid), powertrain/engine/transmission templates, drivers
(interactive, data-driven, path-follower), and terrain (rigid, SCM deformable, CRM granular via
FSI). Ships full vehicle models (HMMWV, M113, Sedan, CityBus, MAN, Kraz, ...) in chrono_models.
Data files live under `data/vehicle/` and load via `veh.SetDataPath(...)`.

## Sensor (chrono_sensor / pychrono.sensor)

GPU-accelerated (OptiX) simulated sensors attached to bodies: camera, lidar, radar, GPS, IMU
(accelerometer/gyro/magnetometer), plus a filter-graph per sensor (noise, save-to-disk,
visualization). Requires an NVIDIA GPU + OptiX at build time.

## FSI / CRM (chrono_fsi)

Fluid-solid interaction via SPH: fluid dynamics and CRM (Continuous Representation Model)
granular/deformable terrain. Rheology options include mu(I) with cohesion and MCC. Couples with
vehicle terrain (`CRMTerrain`).

## DEM (chrono_dem)

GPU discrete-element method for granular dynamics at large particle counts (the code that grew
out of Chrono::GPU). For CPU multicore DEM-style contact there is also chrono_multicore.

## Other modules

- chrono_irrlicht / chrono_vsg: run-time 3D visualization (Irrlicht legacy; VSG current).
- chrono_postprocess: POV-Ray / Blender / gnuplot export.
- chrono_parsers: URDF, OpenSim, Adams, YAML model import; Python engine embedding.
- chrono_modal: modal reduction / eigenanalysis (optional module).
- chrono_synchrono: distributed multi-agent vehicle simulation (MPI/DDS).
- chrono_ros: ROS 2 bridge for vehicles and sensors.
- chrono_fmi: FMU export/import (co-simulation).
- chrono_multicore: OpenMP multicore dynamics (large contact problems on CPU).
- chrono_cascade: OpenCASCADE STEP geometry import.
- chrono_peridynamics: peridynamics for fracture/continuum.
- chrono_matlab / chrono_mumps / chrono_pardisomkl: solver and tooling integrations.
- chrono_models: ready-made vehicle and robot models (also exposed to Python).
- Robots (in chrono_models/robot): Curiosity, VIPER, Turtlebot, RoboSimian, Copters.

## PyChrono specifics

- Import pattern: `import pychrono.core as chrono`, then `pychrono.fea`, `pychrono.vehicle`,
  `pychrono.sensor`, `pychrono.irrlicht` / `pychrono.vsg` as needed.
- Installed via conda (or built with SWIG); not every C++ module is wrapped (e.g. no
  chrono_synchrono in Python; check the demo folders for what is exercised).
- Data path: `chrono.SetChronoDataPath(...)` (+ `veh.SetDataPath(...)` for vehicle assets).
- 10.0 renames trip up older examples: `Set_G_acc` -> `SetGravitationalAcceleration`,
  `ChVectorD` -> `ChVector3d`, `ChFrameD` -> `ChFramed`, `ChFrameMovingD` -> `ChFrameMovingd`.

## Where things live in the source tree

- C++ modules: `src/chrono*/` (one directory per module, listed above).
- C++ demos: `src/demos/<area>/`; Python demos: `src/demos/python/<area>/`
  (core, fea, mbs, vehicle, sensor, fsi, ros, robot, parsers, vsg, yaml, ...).
- Python wrappers: `src/chrono_swig/`; C# wrappers alongside.
- Doxygen manuals: `doxygen/documentation/` (module manuals, tutorials).
