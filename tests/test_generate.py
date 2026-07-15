import json
import math
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

from aprilcube.generate import (
    DICT_MAP,
    FACE_DEFS,
    CubeConfig,
    CubeMeshBuilder,
    TagPatternGenerator,
    _build_rounded_voxel_mesh,
    _marker_corners_on_voxel_face,
    _normal_from_face_def,
    _rounded_box_point,
    _voxel_face_corners,
    build_face_grid,
    load_generation_spec,
    main,
)


def _rounded_config(radius: float = 3.0, segments: int = 5) -> CubeConfig:
    config = CubeConfig(
        grid_x=1,
        grid_y=1,
        grid_z=1,
        dict_id=DICT_MAP["4x4_100"],
        dict_name="4x4_100",
        tag_ids=list(range(6)),
        tag_size_mm=30.0,
        border_cells=1,
        edge_radius_mm=radius,
        edge_segments=segments,
    )
    config.compute()
    return config


def _build_rounded_mesh(config: CubeConfig) -> CubeMeshBuilder:
    builder = CubeMeshBuilder()
    for face_def in FACE_DEFS:
        _rows, _cols, down_cells, right_cells = config.face_layout(face_def)
        grid = np.zeros((down_cells, right_cells), dtype=bool)
        builder.add_face(
            face_def,
            grid,
            config.box_dims,
            config.cell_size,
            config.edge_radius_mm,
            config.edge_segments,
        )
    return builder


def _build_voxel_case(
    occupied: set[tuple[int, int, int]],
) -> tuple[CubeMeshBuilder, list[dict], float]:
    voxel_size = 24.0
    cell_size = 3.0
    face_cells = 8
    marker_pixels = 6
    xs, ys, zs = zip(*occupied)
    min_idx = (min(xs), min(ys), min(zs))
    max_idx = (max(xs), max(ys), max(zs))
    center_abs = tuple(
        (min_idx[axis] + max_idx[axis] + 1) * voxel_size / 2.0
        for axis in range(3)
    )
    tag_gen = TagPatternGenerator(DICT_MAP["4x4_50"])
    records = []
    tag_id = 0
    for voxel in sorted(occupied):
        for face_def in FACE_DEFS:
            neighbor = list(voxel)
            neighbor[face_def[1]] += face_def[2]
            if tuple(neighbor) in occupied:
                continue
            grid = build_face_grid(
                [tag_gen.generate(tag_id)], 1, 1, face_cells, face_cells,
                marker_pixels, 1, False,
            )
            records.append({
                "id": tag_id,
                "face": face_def[0],
                "voxel": list(voxel),
                "normal": list(_normal_from_face_def(face_def)),
                "corners_mm": _marker_corners_on_voxel_face(
                    voxel, face_def, face_cells, marker_pixels,
                    voxel_size, cell_size, center_abs,
                ).tolist(),
                "face_corners_mm": _voxel_face_corners(
                    voxel, face_def, face_cells,
                    voxel_size, cell_size, center_abs,
                ).tolist(),
                "grid": grid,
            })
            tag_id += 1
    builder = _build_rounded_voxel_mesh(
        occupied, records, voxel_size, cell_size, center_abs, 2.0, 3,
    )
    expected_black_area = sum(float(record["grid"].sum()) for record in records) * cell_size ** 2
    return builder, records, expected_black_area


def _assert_watertight(builder: CubeMeshBuilder) -> None:
    edge_counts: dict[tuple[int, int], int] = {}
    for v1, v2, v3, _painted in builder.triangles:
        for a, b in ((v1, v2), (v2, v3), (v3, v1)):
            edge = (min(a, b), max(a, b))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
    assert set(edge_counts.values()) == {2}


def test_rounded_box_keeps_marker_plane_flat():
    dims = (40.0, 40.0, 40.0)
    assert _rounded_box_point((20.0, 15.0, 15.0), dims, 3.0) == pytest.approx(
        (20.0, 15.0, 15.0)
    )

    edge = _rounded_box_point((20.0, 20.0, 0.0), dims, 3.0)
    assert edge == pytest.approx((17.0 + 3.0 / math.sqrt(2),) * 2 + (0.0,))
    assert math.dist(edge[:2], (17.0, 17.0)) == pytest.approx(3.0)

    corner = _rounded_box_point((20.0, 20.0, 20.0), dims, 3.0)
    assert math.dist(corner, (17.0, 17.0, 17.0)) == pytest.approx(3.0)


def test_rounded_mesh_is_watertight_outward_and_within_envelope():
    config = _rounded_config()
    builder = _build_rounded_mesh(config)

    edge_counts: dict[tuple[int, int], int] = {}
    signed_volume = 0.0
    vertices = np.asarray(builder.vertices, dtype=np.float64)
    for v1, v2, v3, _painted in builder.triangles:
        for a, b in ((v1, v2), (v2, v3), (v3, v1)):
            edge = (min(a, b), max(a, b))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1

        p1, p2, p3 = vertices[[v1, v2, v3]]
        normal = np.cross(p2 - p1, p3 - p1)
        assert np.linalg.norm(normal) > 1e-8
        assert float(np.dot(normal, (p1 + p2 + p3) / 3.0)) > 0
        signed_volume += float(np.dot(p1, np.cross(p2, p3))) / 6.0

    assert set(edge_counts.values()) == {2}
    assert np.max(np.abs(vertices), axis=0) == pytest.approx((20.0, 20.0, 20.0))
    assert not np.any(np.all(np.isclose(vertices, (20.0, 20.0, 20.0)), axis=1))
    assert 62_000.0 < signed_volume < 64_000.0


@pytest.mark.parametrize(
    "occupied",
    [
        # T target
        {(1, 0, 0), (1, 0, 1), (1, 0, 2), (0, 0, 2), (2, 0, 2)},
        # U target
        {(0, 0, z) for z in range(3)}
        | {(2, 0, z) for z in range(3)}
        | {(1, 0, 2)},
        # Window frame
        {(x, 0, z) for x in range(4) for z in range(4) if x in {0, 3} or z in {0, 3}},
        # Stair target
        {(0, 0, 0), (1, 0, 0), (2, 0, 0), (1, 0, 1), (2, 0, 1), (2, 0, 2)},
        # Explicit voxel_grid-style L target
        {(0, 0, 0), (1, 0, 0), (0, 0, 1)},
    ],
    ids=["t", "u", "frame", "stair", "voxel_grid_l"],
)
def test_rounded_voxel_shapes_are_watertight_and_keep_tag_paint(
    occupied: set[tuple[int, int, int]],
):
    builder, _records, expected_black_area = _build_voxel_case(occupied)
    _assert_watertight(builder)

    vertices = np.asarray(builder.vertices, dtype=np.float64)
    black_area = 0.0
    for v1, v2, v3, painted in builder.triangles:
        if not painted:
            p1, p2, p3 = vertices[[v1, v2, v3]]
            black_area += float(np.linalg.norm(np.cross(p2 - p1, p3 - p1))) / 2.0
    assert black_area == pytest.approx(expected_black_area, abs=1.0)


def test_rounding_cannot_intrude_into_marker_plane():
    with pytest.raises(ValueError, match="would curve the fiducial plane"):
        _rounded_config(radius=5.1)

    with pytest.raises(ValueError, match="edge_segments"):
        _rounded_config(segments=0)


def test_yaml_geometry_options(tmp_path: Path):
    spec_path = tmp_path / "rounded.yaml"
    spec_path.write_text(
        """
shape:
  type: cuboid
  grid: [1, 1, 1]
geometry:
  edge_radius_mm: 3
  edge_segments: 6
""".strip(),
        encoding="utf-8",
    )
    spec = load_generation_spec(spec_path)
    assert spec.edge_radius_mm == 3.0
    assert spec.edge_segments == 6


def test_cli_generates_valid_rounded_3mf_and_matching_mujoco_mesh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    output = tmp_path / "dex3_safe_cube"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "aprilcube-generate",
            "--grid",
            "1x1x1",
            "--dict",
            "4x4_100",
            "--tag-size",
            "30",
            "--edge-radius",
            "3",
            "--edge-segments",
            "5",
            "--output",
            str(output),
        ],
    )
    main()
    captured = capsys.readouterr()
    assert "non-manifold" not in captured.err

    config_data = json.loads((output / "config.json").read_text(encoding="utf-8"))
    assert config_data["box_dims"] == [40.0, 40.0, 40.0]
    assert config_data["edge_radius_mm"] == 3.0
    assert config_data["edge_segments"] == 5

    with zipfile.ZipFile(output / "cube.3mf") as archive:
        assert archive.testzip() is None
        model = archive.read("3D/Objects/object_1.model").decode("utf-8")
        assert "paint_color=\"8\"" in model
        assert model.count("<triangle ") > 1_000

    obj_text = (output / "mujoco" / "cube.obj").read_text(encoding="utf-8")
    xml_text = (output / "mujoco" / "cube.xml").read_text(encoding="utf-8")
    assert obj_text.count("\nv ") > 1_000
    assert 'type="mesh" mesh="cube_mesh"' in xml_text
    assert "--edge-radius 3" in (output / "README.md").read_text(encoding="utf-8")
