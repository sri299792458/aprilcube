# Running Notes

## Project

- Repository: `https://github.com/younghyopark/aprilcube.git`
- Purpose: Generate 3D-printable ArUco/AprilTag targets and estimate their 6-DOF pose.
- Primary branch: `main`
- Python requirement: 3.10+

## Working Conventions

- Add a dated entry for each meaningful work session.
- Record decisions, files changed, and verification commands/results.
- Keep commits focused and leave the working tree in a clearly documented state.
- Do not rewrite or discard upstream/user changes without explicit approval.

## Session Log

### 2026-07-13 — Initial checkout

- Connected the existing empty Git repository in this workspace to `origin`.
- Fetched and checked out `origin/main` at upstream commit `9d679b5` (`add star history`).
- Added this running project journal.
- No dependencies were installed and no tests were run during checkout setup.

### 2026-07-13 — Bambu H2D test cube

- Selected the tracked `models/1x1x1_30_cube/cube.3mf` model for the first print.
- Target is a 40 x 40 x 40 mm cube with six 30 mm `4x4_100` ArUco markers (IDs 0-5).
- Confirmed the 3MF declares two PLA filaments in black and white, a 0.4 mm nozzle, and Bambu Studio 2.x project metadata.
- Verified the 3MF archive successfully with `python -m zipfile -t models/1x1x1_30_cube/cube.3mf`.
- User will handle slicing and printing in Bambu Studio.

### 2026-07-13 — DEX3 contact-safety review

- Identified a risk that the test cube's exact 90-degree PLA edges and corners could concentrate contact loads on the DEX3 tactile arrays.
- The current mesh generator emits six planar faces with no edge rounding.
- Recommended geometry: continuous 3 mm fillets on all edges and corners, while retaining the centered 30 x 30 mm marker area as a flat plane.
- On the 40 mm cube, a 3 mm radius leaves a 34 x 34 mm planar face and 2 mm of flat white margin around the marker.
- Additional precautions: use the minimum stable grasp force, monitor local pressure readings, and consider replaceable soft corner bumpers for repeated manipulation.
- This 40 mm / 3 mm concept was the preliminary minimum-change option and was superseded by the larger released design below.

### 2026-07-13 — DEX3-safe rounded target geometry implemented

- Added configurable tangent rounded geometry through `--edge-radius` and `--edge-segments`, including YAML support for `cuboid`, `voxel_cuboids`, and `voxel_grid` targets.
- Enforced that the radius cannot exceed the physical outer border, preventing curvature from entering a fiducial plane.
- Updated the printable 3MF, UV-mapped OBJ, MuJoCo collision mesh, generated configuration, preview, and documentation to describe the same geometry.
- Released `models/dex3_safe_cube/cube.3mf`: 50 x 50 x 50 mm, 8 mm edge/corner radius, six 30 mm `4x4_100` markers, and a 2 mm flat white margin outside each marker.
- Selected the 50 mm envelope to match Unitree's published 5 cm hard-object grasp condition; the larger radius is gentler than the preliminary 40 mm / 3 mm concept.
- Added `examples/dex3_safe_cube.yaml`, `docs/dex3_safe_cube_design.md`, and generator regression tests.
- Added OpenCV 5-compatible marker-ID handling in `detect.py`, discovered during detection verification.
- Verification: valid 3MF archive; 3,458 vertices; 6,912 triangles; zero non-manifold edges; 0.0 mm marker-plane error; 34 x 34 mm planar footprint.
- Synthetic detection: 48/48 viewpoints detected and 48/48 passed pose thresholds.
- Cuboids use an analytic tangent rounded box. Voxel-composed targets use a solid-union spherical morphological opening backed by `manifold3d`; this preserves coplanar seams and concave openings while rounding exposed convex features.
- Rejected the initial per-voxel projection approach after it exposed open seams at mixed convex/concave T-junctions. The solid-union replacement is watertight on T, U, frame, stair, and explicit voxel-grid L targets.
- Representative rounded voxel verification: zero non-manifold edges for all five topologies; marker-paint area within 1 mm² of the exact planar pattern in automated tests.
- Focused automated tests: 14 passed (`tests/test_generate.py` and `tests/test_web_app.py`).
- The unfiltered pytest collection still has a pre-existing `tests/test_multicam.py` import error for missing `AuxCamera`; it is unrelated to rounded geometry.

### 2026-07-13 — Detailed engineering report

- Added `docs/dex3_engineering_report.html`, a self-contained-code HTML explanation of the complete DEX3-safe design and implementation.
- The report covers the repository history, contact-pressure rationale, released R8 cube dimensions, analytic cuboid math, topology-aware voxel rounding, rejected per-voxel prototype, marker/color preservation, all generated outputs, OpenCV compatibility fix, validation evidence, H2D print setup, DEX3 commissioning protocol, limitations, exact changed files, and reproduction commands.
- Reused the generated `models/dex3_safe_cube/thumbnail.png` and repository `docs/voxel_shape_gallery.png`; all other engineering diagrams are inline SVG, so no extra image artifacts were added.
- Re-ran the focused tests: 14 passed in 12.62 seconds. Re-tested the 3MF archive successfully and independently recomputed 3,458 vertices, 6,912 triangles, zero non-manifold edges, exact ±25 mm bounds, 117,397.79 mm³ signed volume, and 145.6 g fully-solid PLA estimate.
- Reconfirmed the pre-existing unfiltered pytest collection error for missing `AuxCamera` in `tests/test_multicam.py` and documented it prominently rather than implying a clean repository-wide test run.
- Static HTML audit: 18 sections, no duplicate IDs, no broken internal anchors, no missing local files/images, and valid inline JavaScript syntax.
- The in-app browser refused the local `file://` URL under its security policy; no bypass was attempted, so visual browser rendering remains for the user to inspect when opening the local report.

### 2026-07-13 — Rounded multi-shape visual evidence

- Corrected the engineering report after the user accurately noted that its first revision visually demonstrated only the rounded cube and reused an old sharp-shape gallery for the other families.
- Generated ten separate positive-radius targets through the real output pipeline: a 2x2x1 rectangular cuboid, T, L, stair, U, 3D plus, spiral tower, zigzag snake, window frame, and chair.
- Used R2 mm on 24 mm voxels and R3 mm on the rectangular cuboid and 32 mm spiral voxels; every example retains 1 mm of flat white quiet margin outside its marker planes and uses five surface segments per half-fillet.
- Independently parsed all ten generated 3MF meshes. Every mesh had zero non-manifold edges; complexity ranged from 3,052 vertices / 6,100 triangles for the rectangular cuboid to 9,883 vertices / 19,762 triangles for the chair.
- Added the ten actual final-mesh renders under `docs/rounded_examples/` and expanded `docs/dex3_engineering_report.html` with a visual card and topology row for every shape.
- Inspected T, frame, 3D-plus, and chair renders directly, including preservation of the U/frame-style openings and branched/stepped topology.
- Removed the temporary full model directories after collecting the topology evidence; the tracked example YAML files and documented CLI radius flags reproduce them without committing redundant OBJ/3MF bundles.
- Updated HTML audit: 12 referenced images all readable, no missing local references, no duplicate IDs, no broken internal anchors, and valid inline JavaScript syntax.

### 2026-07-14 — Compact 40 mm / R3 release selected

- The user chose the compact 40 mm target after reviewing the tradeoff against the larger 50 mm / R8 candidate.
- Kept all rounding code generic; no DEX3-specific generator branch was added. Only the application preset, generated model, and current design documentation changed.
- Replaced the released recipe with a 40 x 40 x 40 mm cube, 3 mm tangent radius, five segments per half-fillet, six 30 mm `4x4_100` markers, a 5 mm nominal border, and a 2 mm flat white margin.
- Regenerated `models/dex3_safe_cube/` from `examples/dex3_safe_cube.yaml`, overwriting the former 50 mm print, detector config, preview, README, and MuJoCo assets.
- Updated the root README, usage guide, concise design document, and illustrated engineering report so all current dimensions, commands, diagrams, reasoning, and measurements describe the 40 mm / R3 release. The removed R8 candidate remains only as superseded historical context.
- New mesh verification: valid 34,271-byte 3MF; 1,946 vertices; 3,888 triangles; zero non-manifold edges; exact `[-20, 20]` mm bounds on all axes; 0.0 mm marker-plane error; 63,094.43 mm^3 signed volume; 78.2 g fully-solid PLA estimate at 1.24 g/cm^3.
- Re-ran the 48-view synthetic detector benchmark against the regenerated config: 48/48 detected and within thresholds, with 0.115 degree mean rotation error and 0.20 mm mean translation error.
- Focused automated tests: 14 passed in 17.69 seconds. HTML audit: all 12 images readable, no missing references, duplicate IDs, or broken anchors, and valid inline JavaScript syntax.

### 2026-07-14 — First physical R3 cube print

- The 40 mm / R3 dual-color PLA cube completed and the rounded body, black top field, remaining white cells, and visible side geometry printed cleanly.
- One isolated 5 mm white cell on the top marker has a localized pit/torn surface. This is not present in the generated geometry or slicer preview.
- The localized color-specific failure is most consistent with an incomplete white-nozzle restart or a small deposited blob being dragged during the final top-face toolpath. A top-skin or infill deficiency would be expected to affect a broader area rather than only one isolated white island.
- Do not discard the cube yet. Remove only loose material, fill and level the damaged white cell, then verify top-marker detection before manipulation.
- Future one-shot dual-nozzle guidance must treat the prime tower as necessary but not as a guarantee; the first small island after a nozzle change requires explicit preview/toolpath attention or additional priming margin.

### 2026-07-15 — Algorithm report completed

- Rewrote the superficial algorithm portions of `docs/dex3_engineering_report.html` as a worked technical explanation rather than an output gallery.
- Added numerical 40 mm / R3 point projections, the inner-box/sphere derivation, source-face subdivision stations, shared indexed-vertex construction, winding, continuity, chordal approximation, pseudocode, and direct source-function mappings for analytic cuboids.
- Added a topology-level explanation of why independent voxel rounding fails, a T-junction diagram, formal erosion/dilation set definitions, a worked opening cross-section, opening-versus-closing reasoning, thin-feature limitations, pseudocode, and the exact Manifold operations used by voxel targets.
- Added the missing marker algorithm: black-cell rectangle grouping, shallow cutter construction, intersection/difference partitioning, numerical epsilon and zero-volume filtering, merge canonicalization, and why centroid classification becomes valid only after Boolean partitioning.
- Corrected the stale R8 radius example to the released `3 <= 1 x 5 mm` constraint and documented the retained 2 mm flat quiet margin.
- Removed the ten `docs/rounded_examples/` PNGs and all gallery references because they showed outputs without teaching the algorithms. Numeric watertightness evidence for all ten shapes remains in the report.
- Updated the H2D section with the selected 0.20 mm / two-wall / 10% adaptive-cubic guidance and the first physical print’s localized white-nozzle transition defect.
- Static report audit: 18 sections, eight inline SVG algorithm diagrams, one readable generated cube image, no duplicate IDs, missing anchors, missing local references, or unreadable images, and valid inline JavaScript syntax.
- Automated visual reload of the open local `file://` report was blocked by the in-app browser security policy. No bypass or alternate browser automation was attempted; the user can refresh the already-open report tab for final visual inspection.
- Final verification: 14 focused generator/web tests passed in 5.72 seconds after explicitly adding `.venv/Scripts` to the subprocess PATH; the first invocation’s only failure was that the web CLI executable was not discoverable on PATH. The released 3MF archive test and `git diff --check` also passed.

### 2026-07-15 — Fork publication history squashed

- Created `sri299792458/aprilcube` as a GitHub fork, with local `origin` pointing to the fork and `upstream` preserved as `younghyopark/aprilcube`.
- The first push exposed eight incremental working commits. At the user’s request, rewrote only the fork’s `main` history into one atomic release commit directly above upstream baseline `9d679b5`.
- The squashed tree is identical to the completed working tree; the rewrite changes history presentation, not implementation or generated artifacts.
- Used an explicit force-with-lease against the known prior fork head so a concurrent remote update could not be overwritten silently.

## Current State

- Upstream baseline: `9d679b56cf15be6126c846593fd37471cf8f0ad0`
- Released print candidate: `models/dex3_safe_cube/cube.3mf` (40 mm envelope, R3 mm).
- Reproducible spec: `examples/dex3_safe_cube.yaml`.
- Complete explanation: `docs/dex3_engineering_report.html`.
- Next step: repair the isolated top white cell, verify all six marker IDs with the detector, inspect/deburr the perimeter, then commission manipulation at low grasp force while monitoring tactile load distribution.
