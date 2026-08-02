from pathlib import Path

import cv2
import numpy as np

from aprilcube import CorrespondenceDetector
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
