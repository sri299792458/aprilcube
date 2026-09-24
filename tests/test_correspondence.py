from pathlib import Path

import cv2
import numpy as np
from aprilcube import (
    CorrespondenceDetector,
    CorrespondenceResult,
    TagCorrespondence,
    estimate_pose_diagnostic,
    estimate_pose_hypotheses,
)
from aprilcube.generate import DICT_MAP

MODEL = Path(__file__).parents[1] / "models" / "dex3_safe_cube" / "config.json"


def _marker_image(
    tag_ids: list[int],
    *,
    marker_size: int = 180,
    canvas_size: tuple[int, int] = (640, 480),
) -> np.ndarray:
    width, height = canvas_size
    image = np.full((height, width, 3), 220, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(DICT_MAP["4x4_100"])
    for index, tag_id in enumerate(tag_ids):
        marker = cv2.aruco.generateImageMarker(dictionary, tag_id, marker_size)
        x = 40 + index * (marker_size + 50)
        y = 100
        image[y : y + marker_size, x : x + marker_size] = cv2.cvtColor(
            marker, cv2.COLOR_GRAY2BGR
        )
    return image


def test_current_frame_correspondence_contract() -> None:
    detector = CorrespondenceDetector(MODEL)

    result = detector.detect(_marker_image([5, 0]))

    assert result.valid
    assert result.tag_ids == (0, 5)
    assert result.visible_faces == ("+X", "-Z")
    assert result.duplicate_tag_ids == ()
    assert all(item.image_corners_px.shape == (4, 2) for item in result.observations)
    assert all(item.object_corners_mm.shape == (4, 3) for item in result.observations)
    assert all(item.shortest_side_px > 150 for item in result.observations)


def test_duplicate_id_is_explicitly_rejected() -> None:
    detector = CorrespondenceDetector(MODEL)

    result = detector.detect(_marker_image([0, 0]))

    assert not result.valid
    assert result.tag_ids == ()
    assert result.duplicate_tag_ids == (0,)


def test_blank_frame_does_not_reuse_previous_detection() -> None:
    detector = CorrespondenceDetector(MODEL)
    detected = detector.detect(_marker_image([5]))
    blank = detector.detect(np.full((480, 640, 3), 220, dtype=np.uint8))

    assert detected.tag_ids == (5,)
    assert blank.tag_ids == ()
    assert not blank.valid


def test_object_corner_arrays_are_read_only() -> None:
    detector = CorrespondenceDetector(MODEL)
    result = detector.detect(_marker_image([0]))

    assert len(result.observations) == 1
    assert not result.observations[0].object_corners_mm.flags.writeable


def test_cold_start_planar_pose_selects_lower_error_ippe_branch() -> None:
    """Regress the alternate planar branch observed in a stationary robot burst."""
    observation = TagCorrespondence(
        tag_id=1,
        face_name="-X",
        object_corners_mm=np.array(
            [
                [-20.0, 15.0, 15.0],
                [-20.0, -15.0, 15.0],
                [-20.0, -15.0, -15.0],
                [-20.0, 15.0, -15.0],
            ]
        ),
        image_corners_px=np.array(
            [
                [563.4059448242188, 139.29930114746094],
                [632.8704833984375, 135.0065460205078],
                [636.570068359375, 196.70306396484375],
                [565.8465576171875, 201.14952087402344],
            ]
        ),
        quad_quality=1.0,
        shortest_side_px=61.80733981768639,
        image_margin_px=135.0065460205078,
    )
    result = CorrespondenceResult(
        image_size_wh=(1280, 720),
        observations=(observation,),
    )
    camera_matrix = np.array(
        [
            [905.4686279296875, 0.0, 652.4732055664062],
            [0.0, 905.5797729492188, 368.78778076171875],
            [0.0, 0.0, 1.0],
        ]
    )

    diagnostic = estimate_pose_diagnostic(result, camera_matrix, np.zeros(5))

    assert diagnostic is not None
    np.testing.assert_allclose(
        diagnostic.tvec_mm.reshape(3),
        [-22.27994576, -79.76811601, 406.04182868],
        atol=0.2,
    )
    assert diagnostic.reprojection_error_px < 0.2


def test_planar_pose_hypotheses_expose_both_ippe_branches() -> None:
    observation = TagCorrespondence(
        tag_id=1,
        face_name="-X",
        object_corners_mm=np.array(
            [
                [-20.0, 15.0, 15.0],
                [-20.0, -15.0, 15.0],
                [-20.0, -15.0, -15.0],
                [-20.0, 15.0, -15.0],
            ]
        ),
        image_corners_px=np.array(
            [
                [563.4059448242188, 139.29930114746094],
                [632.8704833984375, 135.0065460205078],
                [636.570068359375, 196.70306396484375],
                [565.8465576171875, 201.14952087402344],
            ]
        ),
        quad_quality=1.0,
        shortest_side_px=61.80733981768639,
        image_margin_px=135.0065460205078,
    )
    result = CorrespondenceResult(
        image_size_wh=(1280, 720),
        observations=(observation,),
    )
    camera_matrix = np.array(
        [
            [905.4686279296875, 0.0, 652.4732055664062],
            [0.0, 905.5797729492188, 368.78778076171875],
            [0.0, 0.0, 1.0],
        ]
    )

    hypotheses = estimate_pose_hypotheses(result, camera_matrix, np.zeros(5))

    assert len(hypotheses) == 2
    assert all(item.source_tag_ids == (1,) for item in hypotheses)
    assert hypotheses[0].reprojection_error_px < hypotheses[1].reprojection_error_px
    np.testing.assert_allclose(
        hypotheses[0].tvec_mm.reshape(3),
        [-22.27994576, -79.76811601, 406.04182868],
        atol=0.2,
    )


def test_multiface_pose_hypotheses_include_individual_and_joint_solutions() -> None:
    camera_matrix = np.array(
        [
            [900.0, 0.0, 640.0],
            [0.0, 900.0, 360.0],
            [0.0, 0.0, 1.0],
        ]
    )
    true_rvec = np.array([[0.15], [-0.25], [0.08]])
    true_tvec = np.array([[40.0], [-20.0], [500.0]])
    faces = (
        (
            1,
            "-X",
            np.array(
                [
                    [-20.0, 15.0, 15.0],
                    [-20.0, -15.0, 15.0],
                    [-20.0, -15.0, -15.0],
                    [-20.0, 15.0, -15.0],
                ]
            ),
        ),
        (
            2,
            "+Y",
            np.array(
                [
                    [-15.0, 20.0, 15.0],
                    [15.0, 20.0, 15.0],
                    [15.0, 20.0, -15.0],
                    [-15.0, 20.0, -15.0],
                ]
            ),
        ),
    )
    observations = []
    for tag_id, face_name, object_points in faces:
        image_points, _ = cv2.projectPoints(
            object_points,
            true_rvec,
            true_tvec,
            camera_matrix,
            np.zeros(5),
        )
        observations.append(
            TagCorrespondence(
                tag_id=tag_id,
                face_name=face_name,
                object_corners_mm=object_points,
                image_corners_px=image_points.reshape(4, 2),
                quad_quality=1.0,
                shortest_side_px=50.0,
                image_margin_px=100.0,
            )
        )
    result = CorrespondenceResult(
        image_size_wh=(1280, 720),
        observations=tuple(observations),
    )

    hypotheses = estimate_pose_hypotheses(result, camera_matrix, np.zeros(5))

    assert len(hypotheses) == 5
    assert {item.source_tag_ids for item in hypotheses} == {(1,), (2,), (1, 2)}
    joint = next(item for item in hypotheses if item.source_tag_ids == (1, 2))
    np.testing.assert_allclose(joint.rvec, true_rvec, atol=1e-6)
    np.testing.assert_allclose(joint.tvec_mm, true_tvec, atol=1e-6)
    assert joint.reprojection_error_px < 1e-6


def test_coplanar_multitag_hypotheses_keep_both_joint_branches() -> None:
    camera_matrix = np.array(
        [
            [900.0, 0.0, 640.0],
            [0.0, 900.0, 360.0],
            [0.0, 0.0, 1.0],
        ]
    )
    true_rvec = np.array([[0.2], [-0.15], [0.05]])
    true_tvec = np.array([[10.0], [20.0], [550.0]])
    tags = (
        (
            1,
            np.array(
                [
                    [-35.0, 15.0, 0.0],
                    [-5.0, 15.0, 0.0],
                    [-5.0, -15.0, 0.0],
                    [-35.0, -15.0, 0.0],
                ]
            ),
        ),
        (
            2,
            np.array(
                [
                    [5.0, 15.0, 0.0],
                    [35.0, 15.0, 0.0],
                    [35.0, -15.0, 0.0],
                    [5.0, -15.0, 0.0],
                ]
            ),
        ),
    )
    observations = []
    for tag_id, object_points in tags:
        image_points, _ = cv2.projectPoints(
            object_points,
            true_rvec,
            true_tvec,
            camera_matrix,
            np.zeros(5),
        )
        observations.append(
            TagCorrespondence(
                tag_id=tag_id,
                face_name="+Z",
                object_corners_mm=object_points,
                image_corners_px=image_points.reshape(4, 2),
                quad_quality=1.0,
                shortest_side_px=45.0,
                image_margin_px=100.0,
            )
        )
    result = CorrespondenceResult(
        image_size_wh=(1280, 720),
        observations=tuple(observations),
    )

    hypotheses = estimate_pose_hypotheses(result, camera_matrix, np.zeros(5))

    joint = [item for item in hypotheses if item.source_tag_ids == (1, 2)]
    assert len(joint) == 2
    assert all(item.inlier_count == 8 for item in joint)
