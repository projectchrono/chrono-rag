# Chrono architecture digest

A curated orientation map of Project Chrono / PyChrono, served by the `chrono_digest` MCP tool
(call it with no argument to list these headings, or with a heading substring to get one section).
For exact code, use `search_chrono` instead. Scope: the Chrono 10.0 release and the current `main`
development branch. Items that exist only on `main` (not in the 10.0.0 release that conda PyChrono
users have) are marked **(main)**; the loaded index's own label says which checkout it was built from.

## Core (chrono / pychrono.core)

The base module every simulation uses. Key pieces:

- `ChSystem` variants: `ChSystemNSC` (non-smooth, complementarity contact) and `ChSystemSMC`
  (smooth, penalty contact). Pick one per simulation; it owns bodies, links, and the solver.
- `ChBody` / `ChBodyEasy*`: rigid bodies (mass, inertia, collision, visual assets).
  `ChBodyEasyBox`, `ChBodyEasySphere`, etc. build body + geometry + collision in one call.
- Links and motors: `ChLink*` joints (revolute, prismatic, spherical, ...), `ChLinkMotor*`
  (rotation/linear, position/speed/torque-driven), `ChLinkTSDA` (spring-damper). **(main)** `ChJoint`
  gained a `CYLINDRICAL` type; rounded primitive shapes and visual-shape type queries were added.
- Math types (10.0 naming): `ChVector3d`, `ChQuaterniond`, `ChFramed`, `ChCoordsysd`.
  Gravity: `system.SetGravitationalAcceleration(ChVector3d(0, 0, -9.81))`.
- Collision: a collision system must be selected (`SetCollisionSystemType`, e.g. BULLET);
  materials are `ChContactMaterialNSC` / `ChContactMaterialSMC`.
- Time stepping: `system.DoStepDynamics(dt)` in a loop; solvers and timesteppers are
  configurable (`SetSolverType`, `SetTimestepperType`). **(main)** Velocity-level constraints and
  end-of-step state updates were reworked; check the CHANGELOG before porting integrator code.
- Output and checkpointing (`chrono/input_output`, `ChOutput`, `ChCheckpoint`): ASCII or HDF5 output
  databases and restartable checkpoints, introduced in 10.0. **(main)** Refactored: `ChOutput::Type`
  became `ChOutput::Format`, a new `ChOutput::Mode` (`FRAMES` vs `SERIES` time histories), custom
  state in checkpoints, and every `ChObj` gets a default name.

## FEA (chrono/fea / pychrono.fea)

Finite-element structures coupled with multibody dynamics: `ChMesh` plus node/element types
(ANCF cable/shell/brick, Euler-Bernoulli beams, IGA beams, BST shells), `ChLinkNodeFrame`-style
constraints tie meshes to bodies. Static (`DoStaticLinear`/`DoStaticNonlinear`) and dynamic
analyses. **(main)** A multiphysics framework (`chrono/fea/multiphysics`) sits alongside the classic
classes: `ChField*` (scalar, temperature, displacement fields), `ChFEModel*` (deformation, thermal,
thermo-deformation), physics-independent `ChFieldElement*` geometry (tet4, hex8), `ChMaterial3D*`
constitutive laws (St.Venant-Kirchhoff, Neo-Hookean, Ogden, thermal, viscous, parallel
composition), FEA loaders (pressure, heat source/flux, convection, radiation), `ChLinkField*`
constraints, and `ChDrawer`/`ChVisualDataExtractor` postprocessing.

## Vehicle (chrono_vehicle / pychrono.vehicle)

Ground-vehicle modeling: wheeled and tracked templates (suspension, steering, driveline, tire
models incl. Pacejka/TMeasy/rigid), powertrain/engine/transmission templates, drivers
(interactive, data-driven, path-follower), and terrain (rigid, SCM deformable, CRM granular via
FSI). Ships full vehicle models (HMMWV, M113, Sedan, CityBus, MAN, Kraz, ...) in chrono_models.
Data files live under `data/vehicle/` and load via `veh.SetDataPath(...)`.
**(main)** API updates: `ChChassis::Construct` is `OnInitialize`; `ChVehicle::Relocate`, vehicle
velocity accessors, TSDA/RSDA functors editable after construction; `ChInteractiveDriver`
`KeyboardMode::HELD` vs `CUMULATIVE`; refactored path-follower controllers and single-wheel rig;
`SCMTerrain` optional GPU backend (`CHRONO_HAS_SCM_GPU`, `SCMTerrainGpu`, CPU reference kept);
M113 FEA options guarded; RoboSimian from URDF.

## Sensor (chrono_sensor / pychrono.sensor)

Simulated sensors attached to bodies: camera, lidar, radar, GPS, IMU (accelerometer/gyro/
magnetometer), plus a filter-graph per sensor (noise, save-to-disk, visualization). In 10.0 the
renderer is NVIDIA OptiX (needs an NVIDIA GPU + OptiX at build time). **(main)** Two vendor-neutral
ray-tracing backends were added: Vulkan RT (`CH_USE_SENSOR_VULKAN_RT`, `ChVulkanCameraSensor`,
GPU or CPU renderer; makes Sensor usable on AMD hardware) and Metal RT on Apple platforms.
`ChScene` became `ChOptixScene`; shaders ship as OptiX-IR; per-RNG streams give a documented
reproducibility contract; Sensor can render FSI-SPH particle systems; shapes without a visual
material render differently than in 10.0.

## FSI / CRM (chrono_fsi)

Fluid-solid interaction via SPH: fluid dynamics (CFD) and CRM (continuous representation method)
granular/deformable terrain. Rheology options include mu(I) with cohesion and MCC. Couples with
vehicle terrain (`CRMTerrain`). **(main)** API and terminology rework: the `elastic_SPH` flag became
the `PhysicsProblem` enum (`CFD`/`CRM`), `SetElasticSPH` became `SetCrmSPH(SoilProperties)`
next to `SetCfdSPH(FluidProperties)`; active domains are per-solid `ChAABB`s
(`SetActiveDomainBody/Mesh1D/Mesh2D`, `SetFreeFlowDuration`); setters throw after `Initialize()`;
double-precision builds fixed. See `demo_FSI-SPH_PlateSinkage` and `demo_YAML_fsi`.

## DEM (chrono_dem)

GPU discrete-element method for granular dynamics at large particle counts (the code that grew
out of Chrono::GPU). For CPU multicore DEM-style contact there is also chrono_multicore.

## GPU backends: CUDA and AMD ROCm/HIP (main)

**(main)** GPU modules (FSI-SPH, DEM, SCM GPU terrain) build against either NVIDIA CUDA or the AMD
ROCm/HIP stack, on Linux and native Windows. Select with the CMake option `CHRONO_GPU_BACKEND`
(`CUDA` or `HIP`); with HIP set `CMAKE_HIP_COMPILER=hipcc` and `CHRONO_HIP_ARCHITECTURES` to the GPU
ISA (gfx942 = MI300, gfx90a = MI200, gfx1151 = Ryzen AI Max iGPU). Code uses vendor-neutral
`gpu`-prefixed wrappers; `CHRONO_HAS_HIP` is defined for HIP builds; the backend is resolved from
the hardware present, not the SDKs installed; `ROCR_VISIBLE_DEVICES` selects devices at run time.
Guides: `docs/README_AMD_GPU.md` (three workflows: CPU PyChrono next to a ROCm ML stack, HIP
FSI/SPH, Sensor), `docs/FSI_SPH_AMD_TUNING.md` and the doxygen manual on tuning FSI-SPH demos for
AMD Instinct. CUDA 13.x / CCCL 3.x, GCC 15, and IntelLLVM are also supported.

## Other modules

- chrono_irrlicht / chrono_vsg: run-time 3D visualization (Irrlicht legacy; VSG current).
- chrono_postprocess: POV-Ray / Blender / gnuplot export.
- chrono_parsers: URDF, OpenSim, Adams, YAML model import; Python engine embedding. **(main)**
  extended YAML and JSON model specification (more joints, loads, output settings).
- chrono_modal: modal reduction / eigenanalysis. **(main)** reduced-model serialization and
  applied loads.
- chrono_synchrono: distributed multi-agent vehicle simulation (MPI/DDS).
- chrono_ros: ROS 2 bridge for vehicles and sensors.
- chrono_fmi: FMU export/import (co-simulation).
- **(main)** chrono_precice: preCICE participant adapters for co-simulation with external solvers
  (`ChPreciceAdapter`, `ChPreciceAdapterMbs`, `ChPreciceAdapterSph`; coupling meshes on rigid
  bodies or FEA nodes; positions/velocities/forces data types).
- chrono_multicore: OpenMP multicore dynamics (large contact problems on CPU).
- chrono_cascade: OpenCASCADE STEP geometry import.
- chrono_peridynamics: peridynamics for fracture/continuum.
- chrono_mumps / chrono_pardisomkl: direct sparse solvers. chrono_matlab exists in 10.0 only:
  **(main)** the Matlab module and `ChSolverMatlab` were removed (Simulink co-simulation over
  TCP/IP via chrono_cosimulation remains).
- chrono_models: ready-made vehicle and robot models (also exposed to Python).
- Robots (in chrono_models/robot): Curiosity, VIPER, Turtlebot, RoboSimian, Copters.

## PyChrono specifics

- Import pattern: `import pychrono.core as chrono`, then `pychrono.fea`, `pychrono.vehicle`,
  `pychrono.sensor`, `pychrono.irrlicht` / `pychrono.vsg` as needed.
- Installed via conda (`conda install projectchrono::pychrono -c conda-forge`; the conda package is
  the 10.0.0 release) or built with SWIG from any checkout; not every C++ module is wrapped (e.g. no
  chrono_synchrono in Python; check the demo folders for what is exercised).
- Data path: `chrono.SetChronoDataPath(...)` (+ `veh.SetDataPath(...)` for vehicle assets).
- 10.0 renames trip up older examples: `Set_G_acc` -> `SetGravitationalAcceleration`,
  `ChVectorD` -> `ChVector3d`, `ChFrameD` -> `ChFramed`, `ChFrameMovingD` -> `ChFrameMovingd`.
- 10.0 added NumPy interoperability for vectors/matrices; **(main)** the `__array__` hooks were
  hardened.

## Where things live in the source tree

- C++ modules: `src/chrono*/` (one directory per module, listed above).
- C++ demos: `src/demos/<area>/`; Python demos: `src/demos/python/<area>/`
  (core, fea, mbs, vehicle, sensor, fsi, ros, robot, parsers, vsg, yaml, ...).
- Python wrappers: `src/chrono_swig/`; C# wrappers alongside.
- Doxygen manuals: `doxygen/documentation/` (module manuals, tutorials, installation guides).
- Platform notes: `PLATFORMS.md`; **(main)** AMD GPU guides under `docs/`.
