# DEX3-Safe AprilCube Design

## Design intent

This target is intended for low-speed manipulation by a Unitree DEX3-1 hand with tactile arrays. It reduces concentrated contact from sharp printed edges while preserving the planar fiducial geometry used for pose estimation.

Rigid PLA is not a compliant protective material. The rounded design reduces the geometric contact singularity, but safe commissioning still requires conservative grasp force and inspection of the printed surface.

## Released geometry

| Parameter | Value |
|---|---:|
| Outer envelope | 40 x 40 x 40 mm |
| Marker dictionary | `4x4_100` |
| Markers | IDs 0-5, one per face |
| Marker size | 30 x 30 mm |
| Nominal white border | 5 mm per side |
| Edge/corner radius | 3 mm |
| Planar face span | 34 x 34 mm |
| Flat margin outside marker | 2 mm per side |
| Surface subdivisions | 5 per half-fillet patch |

The released target uses the compact 40 mm envelope of the repository's original 30 mm-marker cube. A 3 mm radius consumes 3 mm of the available 5 mm border and retains a 2 mm planar white margin outside the marker. This is lighter and easier to grasp than the superseded 50 mm / 8 mm candidate, at the cost of a tighter contact curvature.

The rounded surface is generated as a tangent rounded box. Face centers remain exact planes; edge blends are circular and corner blends are spherical. Relative to the original sharp 40 mm cube, the envelope and marker coordinate frame are unchanged. Because this release replaces a temporary 50 mm candidate, use the regenerated `models/dex3_safe_cube/config.json`; the old 50 mm detector coordinates are not interchangeable.

## Other repository shapes

The contact-safe geometry option is not limited to this cube. `--edge-radius` and the YAML `geometry.edge_radius_mm` field also apply to `voxel_cuboids` and `voxel_grid` targets, including T, U, frame, chair, and stair forms. Those targets are rounded as a complete solid union rather than as independent voxels. This removes sharp exposed convex features without cutting grooves into coplanar seams or filling the intentional concave openings.

For voxel targets, keep the radius within the per-face white border and leave at least one nozzle width of extra flat margin when practical. A common 24 mm voxel / 18 mm marker layout has a 3 mm border; use a 2 mm radius to retain a 1 mm flat margin. Generated 3MF and MuJoCo visual meshes share the rounded geometry; MuJoCo collision boxes remain a conservative sharp envelope.

## Print setup

- Printer: Bambu Lab H2D with 0.4 mm nozzle.
- Materials: black PLA as filament 1 and white PLA as filament 2.
- Layer height: 0.20 mm; use variable layers down to 0.12 mm over the lower fillet if desired.
- Walls: 4 loops.
- Infill: 15-20% gyroid as a starting point.
- Orientation: one marker face flat on the plate.
- Supports: build-plate-only supports under the lower rounded perimeter; keep support painting outside the 30 mm marker plane.
- Seam: paint the seam onto a rounded white edge/corner and away from marker planes.
- Finishing: remove support burrs and sand only the white rounded perimeter with 400-600 grit. Do not sand marker planes.

The planar build-plate footprint is 34 x 34 mm. The unsupported lower fillet expands beyond that footprint, so the support ring is intentional rather than optional for a clean contact surface.

## Acceptance checks

Before robot contact:

1. Reject the part if an edge has a sharp support scar, lifted seam, crack, or delamination.
2. Run a fingertip or cotton swab around every edge; it should not catch on a burr.
3. Confirm every marker plane is flat and free of support material, sanding haze, or color bleed.
4. Verify marker IDs and pose detection before manipulation.
5. Begin with slow closure and the lowest grasp force that prevents slip. Monitor the distribution of tactile readings and stop on a localized spike.

Unitree lists 33 pressure sensors, a 10-2500 g perception range, and a maximum-acceptance test performed with a 1 cm diameter cylinder. That maximum value is not a recommended operating load for a printed edge. See the [official DEX3-1 specifications](https://www.unitree.com/mobile/Dex3-1/).

## Verification results

- 3MF archive integrity: passed.
- Mesh: 1,946 vertices and 3,888 triangles.
- Topology: watertight, with zero non-manifold edges.
- Envelope: exactly `[-20, 20]` mm on X, Y, and Z.
- Marker-plane geometric error: 0.0 mm in the generated mesh.
- Enclosed volume: 63,094.43 mm^3.
- Approximate fully-solid PLA mass at 1.24 g/cm^3: 78.2 g; sliced mass will be lower with infill.
- Synthetic pose regression: 48/48 viewpoints detected and 48/48 within error thresholds.
- Synthetic mean error: 0.115 degrees rotation and 0.20 mm translation.

## Files

- Printable model: `models/dex3_safe_cube/cube.3mf`
- Detector configuration: `models/dex3_safe_cube/config.json`
- Reproducible generation specification: `examples/dex3_safe_cube.yaml`
- Generated preview and print notes: `models/dex3_safe_cube/thumbnail.png` and `README.md`
