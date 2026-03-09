# ArUco Cube — 4x2x2

![Cube preview](thumbnail.png)

## Parameters

| Parameter | Value |
|-----------|-------|
| Dictionary | `4x4_100` |
| Grid | 4x2x2 (X x Y x Z tags) |
| Box dimensions | 87 x 45 x 45 mm |
| Tag size | 18 mm (6x6 cells) |
| Cell size | 3 mm |
| Margin | 1 cell (3 mm) |
| Border | 1 cell (3 mm) |
| Total tags | 40 |
| Tag IDs | 0–39 |

## Face Layout

| Face | Tag IDs |
|------|---------|
| +X | 0, 1, 2, 3 |
| -X | 4, 5, 6, 7 |
| +Y | 8, 9, 10, 11, 12, 13, 14, 15 |
| -Y | 16, 17, 18, 19, 20, 21, 22, 23 |
| +Z | 24, 25, 26, 27, 28, 29, 30, 31 |
| -Z | 32, 33, 34, 35, 36, 37, 38, 39 |

## Files

| File | Description |
|------|-------------|
| `cube.3mf` | Multi-color 3MF for Bambu Studio |
| `config.json` | Detector config (used by `detect_cube.py`) |
| `thumbnail.png` | 6-view preview |
| `mujoco/cube.xml` | MuJoCo MJCF model |
| `mujoco/cube.obj` | Wavefront OBJ mesh (UV-mapped) |
| `mujoco/cube.mtl` | OBJ material file |
| `mujoco/cube_atlas.png` | Texture atlas |

## Config JSON

```json
{
  "dict": "4x4_100",
  "grid": "4x2x2",
  "tag_ids": [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31,
    32,
    33,
    34,
    35,
    36,
    37,
    38,
    39
  ],
  "faces": {
    "+X": [
      0,
      1,
      2,
      3
    ],
    "-X": [
      4,
      5,
      6,
      7
    ],
    "+Y": [
      8,
      9,
      10,
      11,
      12,
      13,
      14,
      15
    ],
    "-Y": [
      16,
      17,
      18,
      19,
      20,
      21,
      22,
      23
    ],
    "+Z": [
      24,
      25,
      26,
      27,
      28,
      29,
      30,
      31
    ],
    "-Z": [
      32,
      33,
      34,
      35,
      36,
      37,
      38,
      39
    ]
  },
  "tag_size_mm": 18.0,
  "cell_size_mm": 3.0,
  "margin_cells": 1,
  "border_cells": 1,
  "marker_pixels": 6,
  "box_dims": [
    87.0,
    45.0,
    45.0
  ]
}
```

## Regenerate

```bash
python generate_cube.py --grid 4x2x2 --dict 4x4_100 --tag-size 18 --margin-cell 1 --border-cell 1 -o 4x2x2_18_cube
```
