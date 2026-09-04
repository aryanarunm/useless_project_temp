import os
import sys
import ctypes
import platform
import urllib.request
import numpy as np
import cv2
import mediapipe as mp

# Apply Windows Python 3.13 ctypes patch for MediaPipe if required
if platform.system() == 'Windows':
    try:
        from mediapipe.tasks.python.core import mediapipe_c_bindings as mcb
        _orig_load_raw = mcb.load_raw_library

        def _patched_load_raw(signatures=()):
            msvcrt = ctypes.cdll.msvcrt
            try:
                return _orig_load_raw(signatures)
            except AttributeError as e:
                if "'free' not found" in str(e):
                    import importlib.resources as resources
                    lib_path_context = resources.files('mediapipe.tasks.c')
                    absolute_lib_path = str(lib_path_context / 'libmediapipe.dll')
                    _shared_lib = ctypes.CDLL(absolute_lib_path)
                    for signature in signatures:
                        c_func = getattr(_shared_lib, signature.func_name)
                        c_func.argtypes = signature.argtypes
                        c_func.restype = signature.restype
                    _shared_lib.free = msvcrt.free
                    _shared_lib.free.argtypes = [ctypes.c_void_p]
                    _shared_lib.free.restype = None
                    return _shared_lib
                raise e
        mcb.load_raw_library = _patched_load_raw
    except Exception:
        pass

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

# MediaPipe inner lip landmarks indices (ordered loop)
INNER_LIP_INDICES = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95]
UPPER_LIP_CENTER_IDX = 13
LOWER_LIP_CENTER_IDX = 14
LEFT_MOUTH_CORNER_IDX = 61
RIGHT_MOUTH_CORNER_IDX = 291

class TongueDetector:
    def __init__(self, model_path="face_landmarker.task", min_mouth_open_ratio=0.08, max_grace_frames=6):
        self.model_path = model_path
        self.min_mouth_open_ratio = min_mouth_open_ratio
        self.max_grace_frames = max_grace_frames
        
        # State tracking for hysteresis & grace persistence
        self.smoothed_tip = None
        self.velocity = np.array([0.0, 0.0], dtype=np.float32)
        self.lost_frames = 0
        self.is_tracking_active = False

        # ROI stabilization window
        self.prev_roi = None

        self._ensure_model_exists()
        
        # Initialize CLAHE contrast enhancer
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        # Initialize FaceLandmarker
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.4,
            min_face_presence_confidence=0.4,
            min_tracking_confidence=0.4
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)

    def _ensure_model_exists(self):
        if not os.path.exists(self.model_path):
            alt_path = os.path.join(os.path.dirname(__file__), "..", self.model_path)
            if os.path.exists(alt_path):
                self.model_path = alt_path
                return
            print(f"[TongueDetector] Downloading MediaPipe model...")
            try:
                urllib.request.urlretrieve(MODEL_URL, self.model_path)
            except Exception as e:
                raise RuntimeError(f"Failed to download MediaPipe model: {e}")

    def close(self):
        if hasattr(self, 'landmarker') and self.landmarker is not None:
            try:
                self.landmarker.close()
            except Exception:
                pass
            self.landmarker = None

    def reset_tracking(self):
        self.smoothed_tip = None
        self.velocity = np.array([0.0, 0.0], dtype=np.float32)
        self.lost_frames = 0
        self.is_tracking_active = False
        self.prev_roi = None

    def process_frame(self, frame_bgr):
        h, w, c = frame_bgr.shape
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        
        result = self.landmarker.detect(mp_img)
        
        res_data = {
            'face_detected': False,
            'mouth_open': False,
            'mouth_ratio': 0.0,
            'tongue_detected': False,
            'tongue_tip': None,
            'smoothed_tip': None,
            'direction': 'NONE',
            'mouth_polygon': [],
            'roi_mask': None,
            'roi_box': None,
            'in_grace_period': False
        }

        if not result.face_landmarks or len(result.face_landmarks) == 0:
            return self._handle_detection_failure(res_data)

        res_data['face_detected'] = True
        landmarks = result.face_landmarks[0]

        def lm_pt(idx):
            return int(landmarks[idx].x * w), int(landmarks[idx].y * h)

        upper_lip = np.array(lm_pt(UPPER_LIP_CENTER_IDX))
        lower_lip = np.array(lm_pt(LOWER_LIP_CENTER_IDX))
        left_corner = np.array(lm_pt(LEFT_MOUTH_CORNER_IDX))
        right_corner = np.array(lm_pt(RIGHT_MOUTH_CORNER_IDX))

        vertical_dist = np.linalg.norm(lower_lip - upper_lip)
        horizontal_dist = np.linalg.norm(right_corner - left_corner) + 1e-6
        mouth_ratio = vertical_dist / horizontal_dist
        res_data['mouth_ratio'] = float(mouth_ratio)

        polygon_pts = [lm_pt(idx) for idx in INNER_LIP_INDICES]
        res_data['mouth_polygon'] = polygon_pts

        # Hysteresis thresholding for mouth open state
        open_threshold = self.min_mouth_open_ratio if not self.is_tracking_active else (self.min_mouth_open_ratio * 0.65)

        if mouth_ratio < open_threshold:
            return self._handle_detection_failure(res_data)

        res_data['mouth_open'] = True

        # Extract mouth ROI with generous 25% margin
        poly_arr = np.array(polygon_pts, dtype=np.int32)
        rx, ry, rw, rh = cv2.boundingRect(poly_arr)
        margin = int(max(rw, rh) * 0.25)
        curr_roi = np.array([max(0, rx - margin), max(0, ry - margin), min(w, rx + rw + margin), min(h, ry + rh + margin)], dtype=np.float32)

        # Smooth ROI box over time to prevent boundary jitter
        if self.prev_roi is None:
            self.prev_roi = curr_roi
        else:
            self.prev_roi = 0.3 * curr_roi + 0.7 * self.prev_roi

        rx1, ry1, rx2, ry2 = self.prev_roi.astype(int)
        res_data['roi_box'] = (rx1, ry1, rx2 - rx1, ry2 - ry1)

        roi_bgr = frame_bgr[ry1:ry2, rx1:rx2]
        if roi_bgr.size == 0:
            return self._handle_detection_failure(res_data)

        # Inner mouth polygon mask
        mask_poly = np.zeros((ry2 - ry1, rx2 - rx1), dtype=np.uint8)
        shifted_poly = poly_arr - np.array([rx1, ry1])
        cv2.fillPoly(mask_poly, [shifted_poly], 255)

        # CLAHE equalization on V and L channels
        roi_hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        roi_hsv[:, :, 2] = self.clahe.apply(roi_hsv[:, :, 2])

        roi_lab = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2LAB)
        roi_lab[:, :, 0] = self.clahe.apply(roi_lab[:, :, 0])

        # HSV Thresholds
        lower_hsv1 = np.array([0, 25, 30], dtype=np.uint8)
        upper_hsv1 = np.array([28, 255, 255], dtype=np.uint8)
        lower_hsv2 = np.array([150, 25, 30], dtype=np.uint8)
        upper_hsv2 = np.array([180, 255, 255], dtype=np.uint8)

        mask_hsv = cv2.bitwise_or(
            cv2.inRange(roi_hsv, lower_hsv1, upper_hsv1),
            cv2.inRange(roi_hsv, lower_hsv2, upper_hsv2)
        )

        # LAB Thresholds for redness
        a_channel = roi_lab[:, :, 1]
        _, mask_lab = cv2.threshold(a_channel, 130, 255, cv2.THRESH_BINARY)

        combined_color = cv2.bitwise_or(mask_hsv, mask_lab)
        tongue_mask = cv2.bitwise_and(combined_color, mask_poly)

        # Morphological smoothing
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        tongue_mask = cv2.morphologyEx(tongue_mask, cv2.MORPH_OPEN, kernel_open)
        tongue_mask = cv2.morphologyEx(tongue_mask, cv2.MORPH_CLOSE, kernel_close)
        res_data['roi_mask'] = tongue_mask

        # Find tongue contours
        contours, _ = cv2.findContours(tongue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours = [c for c in contours if cv2.contourArea(c) >= 12]

        if not valid_contours:
            return self._handle_detection_failure(res_data)

        # Select largest valid tongue blob
        largest_cnt = max(valid_contours, key=cv2.contourArea)
        pts_in_roi = largest_cnt.reshape(-1, 2)
        pts_global = pts_in_roi + np.array([rx1, ry1])

        # STABILIZED TIP CALCULATION:
        # Instead of taking a single extreme vertex (which causes wobble),
        # take the top 5% farthest points relative to upper lip center and compute their centroid!
        dists = np.linalg.norm(pts_global - upper_lip, axis=1)
        top_k = max(1, int(len(dists) * 0.08))
        farthest_indices = np.argsort(dists)[-top_k:]
        raw_tip = np.mean(pts_global[farthest_indices], axis=0).astype(np.float32)

        # Successful detection -> Update state
        self.lost_frames = 0
        self.is_tracking_active = True

        # STABILIZED DUAL-STAGE ADAPTIVE EMA FILTER:
        # High stability at low speeds (zero wobble), responsive at high speeds
        if self.smoothed_tip is None:
            self.smoothed_tip = raw_tip.copy()
            self.velocity = np.array([0.0, 0.0], dtype=np.float32)
        else:
            disp = np.linalg.norm(raw_tip - self.smoothed_tip)
            # Adaptive alpha tuning:
            if disp < 3.0:
                alpha = 0.12 # Ultra-stable when hovering/slow
            elif disp < 10.0:
                alpha = 0.22 # Smooth medium speed
            else:
                alpha = 0.38 # Fast response

            new_smooth = alpha * raw_tip + (1.0 - alpha) * self.smoothed_tip
            self.velocity = 0.7 * self.velocity + 0.3 * (new_smooth - self.smoothed_tip)
            self.smoothed_tip = new_smooth

        smoothed_pt = (int(round(self.smoothed_tip[0])), int(round(self.smoothed_tip[1])))

        res_data['tongue_detected'] = True
        res_data['tongue_tip'] = (int(raw_tip[0]), int(raw_tip[1]))
        res_data['smoothed_tip'] = smoothed_pt

        # Determine directional vector
        mouth_center = (upper_lip + lower_lip) / 2.0
        dx = smoothed_pt[0] - mouth_center[0]
        dy = smoothed_pt[1] - mouth_center[1]
        thresh = horizontal_dist * 0.12

        if abs(dx) > abs(dy):
            res_data['direction'] = 'RIGHT' if dx > thresh else ('LEFT' if dx < -thresh else 'CENTER')
        else:
            res_data['direction'] = 'DOWN' if dy > thresh else ('UP' if dy < -thresh else 'CENTER')

        return res_data

    def _handle_detection_failure(self, res_data):
        if self.is_tracking_active and self.smoothed_tip is not None and self.lost_frames < self.max_grace_frames:
            self.lost_frames += 1
            decay = max(0.0, 1.0 - (self.lost_frames / float(self.max_grace_frames + 1)))
            self.smoothed_tip += self.velocity * decay * 0.4

            smoothed_pt = (int(round(self.smoothed_tip[0])), int(round(self.smoothed_tip[1])))
            res_data['tongue_detected'] = True
            res_data['smoothed_tip'] = smoothed_pt
            res_data['in_grace_period'] = True
            res_data['direction'] = 'HOLD'
            return res_data

        self.reset_tracking()
        return res_data
