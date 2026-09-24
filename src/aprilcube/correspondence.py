"""Stateless 2D/3D correspondences for calibration measurements.

This module intentionally excludes pose history, optical flow, temporal
filtering, prediction, and rejected-quad recovery.  A result describes only
markers decoded in the image passed to that call.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from aprilcube.detect import (
    _planar_pose_candidates,
    _preprocess,
    _quad_quality,
    build_tag_corner_map,
    create_detector,
    estimate_pose,
    load_cube_config,
)


@dataclass(frozen=True, slots=True)
class TagCorrespondence:
    """One decoded tag with identically ordered image and object corners."""

    tag_id: int
    face_name: str | None
    image_corners_px: np.ndarray
    object_corners_mm: np.ndarray
    quad_quality: float
    shortest_side_px: float
    image_margin_px: float

    def __post_init__(self) -> None:
        image_corners = np.asarray(self.image_corners_px, dtype=np.float64).copy()
        object_corners = np.asarray(self.object_corners_mm, dtype=np.float64).copy()
        if image_corners.shape != (4, 2):
            raise ValueError(
                f"image_corners_px must have shape (4, 2), got {image_corners.shape}"
            )
        if object_corners.shape != (4, 3):
            raise ValueError(
                f"object_corners_mm must have shape (4, 3), got {object_corners.shape}"
            )
        image_corners.setflags(write=False)
        object_corners.setflags(write=False)
        object.__setattr__(self, "image_corners_px", image_corners)
        object.__setattr__(self, "object_corners_mm", object_corners)


@dataclass(frozen=True, slots=True)
class CorrespondenceResult:
    """Current-frame decoded observations and explicit rejection metadata."""

    image_size_wh: tuple[int, int]
    observations: tuple[TagCorrespondence, ...]
    duplicate_tag_ids: tuple[int, ...] = ()
    ignored_tag_ids: tuple[int, ...] = ()
    opencv_rejected_candidates: int = 0
    quality_rejected_detections: int = 0

    @property
    def valid(self) -> bool:
        """Whether the frame has usable, unambiguous correspondences."""
        return bool(self.observations) and not self.duplicate_tag_ids

    @property
    def tag_ids(self) -> tuple[int, ...]:
        return tuple(item.tag_id for item in self.observations)

    @property
    def visible_faces(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    item.face_name
                    for item in self.observations
                    if item.face_name is not None
                }
            )
        )


@dataclass(frozen=True, slots=True)
class PoseDiagnostic:
    """Stateless PnP diagnostic; never a replacement for raw corners."""

    rvec: np.ndarray
    tvec_mm: np.ndarray
    reprojection_error_px: float
    inlier_count: int

    def __post_init__(self) -> None:
        rvec = np.asarray(self.rvec, dtype=np.float64).reshape(3, 1).copy()
        tvec = np.asarray(self.tvec_mm, dtype=np.float64).reshape(3, 1).copy()
        rvec.setflags(write=False)
        tvec.setflags(write=False)
        object.__setattr__(self, "rvec", rvec)
        object.__setattr__(self, "tvec_mm", tvec)


@dataclass(frozen=True, slots=True)
class PoseHypothesis:
    """One stateless current-frame pose candidate and its supporting tags."""

    rvec: np.ndarray
    tvec_mm: np.ndarray
    reprojection_error_px: float
    inlier_count: int
    source_tag_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        rvec = np.asarray(self.rvec, dtype=np.float64).reshape(3, 1).copy()
        tvec = np.asarray(self.tvec_mm, dtype=np.float64).reshape(3, 1).copy()
        rvec.setflags(write=False)
        tvec.setflags(write=False)
        object.__setattr__(self, "rvec", rvec)
        object.__setattr__(self, "tvec_mm", tvec)
        object.__setattr__(
            self,
            "source_tag_ids",
            tuple(int(tag_id) for tag_id in self.source_tag_ids),
        )
        if not np.isfinite(self.reprojection_error_px) or self.reprojection_error_px < 0:
            raise ValueError("reprojection_error_px must be finite and non-negative")
        if self.inlier_count < 0:
            raise ValueError("inlier_count must be non-negative")
        if not self.source_tag_ids or len(set(self.source_tag_ids)) != len(
            self.source_tag_ids
        ):
            raise ValueError("source_tag_ids must be non-empty and unique")


class CorrespondenceDetector:
    """Decode deterministic, current-frame AprilCube correspondences."""

    def __init__(
        self,
        cube_cfg: str | Path,
        *,
        preprocess: bool = True,
        minimum_quad_quality: float = 0.15,
    ) -> None:
        cube_path = Path(cube_cfg)
        if cube_path.is_dir():
            cube_path = cube_path / "config.json"
        config, face_id_sets = load_cube_config(str(cube_path))

        if not 0.0 <= minimum_quad_quality <= 1.0:
            raise ValueError("minimum_quad_quality must be between 0 and 1")

        self.cube_path = cube_path
        self.config = config
        self.face_id_sets = face_id_sets
        self.tag_corner_map = build_tag_corner_map(config)
        self.valid_ids = frozenset(self.tag_corner_map)
        self.preprocess = preprocess
        self.minimum_quad_quality = float(minimum_quad_quality)
        self._detector = create_detector(config.dict_id, fast=False)
        self._face_for_id = {
            int(tag_id): face_name
            for face_name, tag_ids in face_id_sets.items()
            for tag_id in tag_ids
        }

    def detect_correspondences(self, image: np.ndarray) -> CorrespondenceResult:
        """Return only tags decoded in ``image``, sorted by tag ID.

        Duplicate instances of a valid ID are excluded entirely and reported in
        ``duplicate_tag_ids`` so callers cannot silently choose one instance.
        """
        frame = np.asarray(image)
        if frame.ndim not in (2, 3):
            raise ValueError(f"image must have 2 or 3 dimensions, got {frame.ndim}")
        if frame.ndim == 3 and frame.shape[2] not in (3, 4):
            raise ValueError(
                f"color image must have 3 or 4 channels, got {frame.shape[2]}"
            )
        if frame.size == 0:
            raise ValueError("image must not be empty")

        if frame.ndim == 2:
            gray = frame
        elif frame.shape[2] == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        if gray.dtype != np.uint8:
            raise ValueError(f"image dtype must be uint8, got {gray.dtype}")

        detector_input = _preprocess(gray) if self.preprocess else gray
        try:
            corners_list, ids, rejected = self._detector.detectMarkers(detector_input)
        except cv2.error:
            corners_list, ids, rejected = (), None, ()

        candidates: dict[int, list[tuple[np.ndarray, float]]] = {}
        ignored_ids: set[int] = set()
        quality_rejected = 0
        if ids is not None:
            for raw_id, raw_corners in zip(ids, corners_list, strict=True):
                tag_id = int(np.asarray(raw_id).reshape(-1)[0])
                if tag_id not in self.valid_ids:
                    ignored_ids.add(tag_id)
                    continue
                corners = np.asarray(raw_corners, dtype=np.float64).reshape(4, 2)
                quality = float(_quad_quality(corners))
                if quality < self.minimum_quad_quality:
                    quality_rejected += 1
                    continue
                candidates.setdefault(tag_id, []).append((corners, quality))

        duplicate_ids = tuple(
            sorted(tag_id for tag_id, items in candidates.items() if len(items) > 1)
        )
        height, width = gray.shape
        observations: list[TagCorrespondence] = []
        for tag_id in sorted(candidates):
            items = candidates[tag_id]
            if len(items) != 1:
                continue
            corners, quality = items[0]
            sides = np.linalg.norm(np.roll(corners, -1, axis=0) - corners, axis=1)
            x = corners[:, 0]
            y = corners[:, 1]
            margin = float(
                np.min(
                    np.concatenate(
                        (
                            x,
                            (width - 1) - x,
                            y,
                            (height - 1) - y,
                        )
                    )
                )
            )
            observations.append(
                TagCorrespondence(
                    tag_id=tag_id,
                    face_name=self._face_for_id.get(tag_id),
                    image_corners_px=corners,
                    object_corners_mm=self.tag_corner_map[tag_id],
                    quad_quality=quality,
                    shortest_side_px=float(np.min(sides)),
                    image_margin_px=margin,
                )
            )

        return CorrespondenceResult(
            image_size_wh=(width, height),
            observations=tuple(observations),
            duplicate_tag_ids=duplicate_ids,
            ignored_tag_ids=tuple(sorted(ignored_ids)),
            opencv_rejected_candidates=len(rejected or ()),
            quality_rejected_detections=quality_rejected,
        )

    def detect(self, image: np.ndarray) -> CorrespondenceResult:
        """Alias for :meth:`detect_correspondences`."""
        return self.detect_correspondences(image)


def correspondence_detector(
    cube_cfg: str | Path,
    *,
    preprocess: bool = True,
    minimum_quad_quality: float = 0.15,
) -> CorrespondenceDetector:
    """Construct the public stateless correspondence detector."""
    return CorrespondenceDetector(
        cube_cfg,
        preprocess=preprocess,
        minimum_quad_quality=minimum_quad_quality,
    )


def estimate_pose_diagnostic(
    result: CorrespondenceResult,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray | None = None,
) -> PoseDiagnostic | None:
    """Estimate a current-frame cube pose for preview quality diagnostics.

    Calibration consumers should still minimize the raw 2D corner residuals.
    This helper exists for overlays and multi-face geometry consistency checks.
    """
    if not result.valid:
        return None
    object_points = np.vstack(
        [item.object_corners_mm for item in result.observations]
    ).astype(np.float64)
    image_points = np.vstack(
        [item.image_corners_px for item in result.observations]
    ).astype(np.float64)
    matrix = np.asarray(camera_matrix, dtype=np.float64)
    if matrix.shape != (3, 3):
        raise ValueError(f"camera_matrix must have shape (3, 3), got {matrix.shape}")
    distortion = (
        np.zeros(5, dtype=np.float64)
        if dist_coeffs is None
        else np.asarray(dist_coeffs, dtype=np.float64)
    )
    success, rvec, tvec, error, inliers = estimate_pose(
        object_points,
        image_points,
        matrix,
        distortion,
    )
    if not success or rvec is None or tvec is None:
        return None
    return PoseDiagnostic(
        rvec=rvec,
        tvec_mm=tvec,
        reprojection_error_px=float(error),
        inlier_count=0 if inliers is None else len(inliers),
    )


def estimate_pose_hypotheses(
    result: CorrespondenceResult,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray | None = None,
) -> tuple[PoseHypothesis, ...]:
    """Return every current-frame planar branch and the joint face estimate.

    Each decoded face contributes all positive-depth IPPE solutions.  When
    multiple faces are visible, their joint non-planar estimate is included as
    an additional hypothesis.  This function is deliberately stateless: it
    does not choose a branch using pose history or a scene-specific prior.
    """
    if not result.valid:
        return ()
    matrix = np.asarray(camera_matrix, dtype=np.float64)
    if matrix.shape != (3, 3):
        raise ValueError(f"camera_matrix must have shape (3, 3), got {matrix.shape}")
    distortion = (
        np.zeros(5, dtype=np.float64)
        if dist_coeffs is None
        else np.asarray(dist_coeffs, dtype=np.float64)
    )

    hypotheses: list[PoseHypothesis] = []

    def append_planar_hypotheses(
        object_points: np.ndarray,
        image_points: np.ndarray,
        source_tag_ids: tuple[int, ...],
    ) -> None:
        candidates = _planar_pose_candidates(
            object_points,
            image_points,
            matrix,
            distortion,
        )
        for _raw_error, raw_rvec, raw_tvec in candidates:
            try:
                rvec, tvec = cv2.solvePnPRefineLM(
                    objectPoints=object_points,
                    imagePoints=image_points,
                    cameraMatrix=matrix,
                    distCoeffs=distortion,
                    rvec=raw_rvec,
                    tvec=raw_tvec,
                )
            except cv2.error:
                continue
            rotation, _ = cv2.Rodrigues(rvec)
            camera_points = (rotation @ object_points.T + tvec.reshape(3, 1)).T
            if np.min(camera_points[:, 2]) <= 0:
                continue
            projected, _ = cv2.projectPoints(
                object_points,
                rvec,
                tvec,
                matrix,
                distortion,
            )
            error = float(
                np.mean(
                    np.linalg.norm(
                        image_points - projected.reshape(-1, 2),
                        axis=1,
                    )
                )
            )
            hypotheses.append(
                PoseHypothesis(
                    rvec=rvec,
                    tvec_mm=tvec,
                    reprojection_error_px=error,
                    inlier_count=len(object_points),
                    source_tag_ids=source_tag_ids,
                )
            )

    for observation in result.observations:
        append_planar_hypotheses(
            np.asarray(observation.object_corners_mm, dtype=np.float64),
            np.asarray(observation.image_corners_px, dtype=np.float64),
            (observation.tag_id,),
        )

    if len(result.observations) > 1:
        joint_object_points = np.vstack(
            [item.object_corners_mm for item in result.observations]
        ).astype(np.float64)
        joint_image_points = np.vstack(
            [item.image_corners_px for item in result.observations]
        ).astype(np.float64)
        centered_object_points = joint_object_points - np.mean(
            joint_object_points,
            axis=0,
        )
        if np.linalg.matrix_rank(centered_object_points) == 2:
            append_planar_hypotheses(
                joint_object_points,
                joint_image_points,
                result.tag_ids,
            )
        else:
            joint = estimate_pose_diagnostic(result, matrix, distortion)
            if joint is not None:
                joint_rotation, _ = cv2.Rodrigues(joint.rvec)
                joint_camera_points = (
                    joint_rotation @ joint_object_points.T
                    + joint.tvec_mm.reshape(3, 1)
                ).T
                if np.min(joint_camera_points[:, 2]) > 0:
                    hypotheses.append(
                        PoseHypothesis(
                            rvec=joint.rvec,
                            tvec_mm=joint.tvec_mm,
                            reprojection_error_px=joint.reprojection_error_px,
                            inlier_count=joint.inlier_count,
                            source_tag_ids=result.tag_ids,
                        )
                    )

    return tuple(
        sorted(
            hypotheses,
            key=lambda item: (
                item.reprojection_error_px,
                item.source_tag_ids,
                tuple(item.tvec_mm.reshape(3)),
                tuple(item.rvec.reshape(3)),
            ),
        )
    )
