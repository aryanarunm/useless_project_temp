import os
import sys
import time
import argparse
import ctypes
import numpy as np
import cv2
from detector import TongueDetector
from minimal_hud import MinimalHUD

# Windows User32 API for native high-performance mouse control
try:
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()  # Native screen resolution handling
    SCREEN_WIDTH = user32.GetSystemMetrics(0)
    SCREEN_HEIGHT = user32.GetSystemMetrics(1)
except Exception:
    SCREEN_WIDTH = 1920
    SCREEN_HEIGHT = 1080

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

def move_mouse(x, y):
    """Moves system cursor to screen coordinates (x, y) bounded by screen dimensions."""
    clamped_x = max(0, min(SCREEN_WIDTH - 1, int(round(x))))
    clamped_y = max(0, min(SCREEN_HEIGHT - 1, int(round(y))))
    ctypes.windll.user32.SetCursorPos(clamped_x, clamped_y)

def single_click():
    """Triggers a native Windows single left mouse click."""
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

def double_click():
    """Triggers a native Windows double left mouse click."""
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

class TongueMouseController:
    def __init__(self, sensitivity=0.85, smoothing=0.18, enable_double_click=True):
        self.sensitivity = sensitivity
        self.smoothing = smoothing
        self.enable_double_click = enable_double_click

        self.screen_w = SCREEN_WIDTH
        self.screen_h = SCREEN_HEIGHT

        self.curr_mouse_x = float(self.screen_w // 2)
        self.curr_mouse_y = float(self.screen_h // 2)

        self.last_stable_x = self.curr_mouse_x
        self.last_stable_y = self.curr_mouse_y

        self.mouth_was_open = False
        self.click_feedback_time = 0
        self.last_click_type = ""

        self.center_x = None
        self.center_y = None

    def process_mouse_control(self, detection_res, frame_w, frame_h):
        smoothed_tip = detection_res.get('smoothed_tip')
        mouth_open = detection_res.get('mouth_open', False)
        mouth_ratio = detection_res.get('mouth_ratio', 0.0)
        tracking = False

        if mouth_open and smoothed_tip is not None and mouth_ratio >= 0.070:
            tracking = True
            tx, ty = smoothed_tip

            if self.center_x is None:
                self.center_x = tx
                self.center_y = ty

            dx = (tx - self.center_x) / float(frame_w * 0.22)
            dy = (ty - self.center_y) / float(frame_h * 0.22)

            if abs(dx) < 0.04:
                dx = 0.0
            if abs(dy) < 0.04:
                dy = 0.0

            dx = np.sign(dx) * (abs(dx) ** 1.05) * self.sensitivity
            dy = np.sign(dy) * (abs(dy) ** 1.05) * self.sensitivity

            target_x = (self.screen_w / 2.0) + (dx * (self.screen_w / 2.0))
            target_y = (self.screen_h / 2.0) + (dy * (self.screen_h / 2.0))

            self.curr_mouse_x = (1.0 - self.smoothing) * self.curr_mouse_x + self.smoothing * target_x
            self.curr_mouse_y = (1.0 - self.smoothing) * self.curr_mouse_y + self.smoothing * target_y

            self.last_stable_x = self.curr_mouse_x
            self.last_stable_y = self.curr_mouse_y

            move_mouse(self.curr_mouse_x, self.curr_mouse_y)
            self.mouth_was_open = True

        elif self.mouth_was_open and mouth_ratio < 0.070 and mouth_ratio > 0.045:
            move_mouse(self.last_stable_x, self.last_stable_y)

        elif self.mouth_was_open and not mouth_open:
            move_mouse(self.last_stable_x, self.last_stable_y)

            if self.enable_double_click:
                print(f"[TongueMouse] Mouth closed -> DOUBLE CLICK locked at ({int(self.last_stable_x)}, {int(self.last_stable_y)})")
                double_click()
                self.last_click_type = "DOUBLE CLICK"
            else:
                print(f"[TongueMouse] Mouth closed -> SINGLE CLICK locked at ({int(self.last_stable_x)}, {int(self.last_stable_y)})")
                single_click()
                self.last_click_type = "SINGLE CLICK"

            self.click_feedback_time = time.time()
            self.mouth_was_open = False
            self.center_x = None

        active_click = self.last_click_type if (time.time() - self.click_feedback_time) < 1.0 else ""

        return {
            'mouse_x': int(self.last_stable_x if not mouth_open else self.curr_mouse_x),
            'mouse_y': int(self.last_stable_y if not mouth_open else self.curr_mouse_y),
            'click_event': active_click,
            'tracking': tracking
        }

def main():
    parser = argparse.ArgumentParser(description="Tongue Tip Mouse Controller (Minimal Pitch Black Dark Mode)")
    parser.add_argument("--source", type=str, default="0", help="Webcam device index (e.g. 0)")
    parser.add_argument("--sensitivity", type=float, default=0.85, help="Mouse sensitivity multiplier (default: 0.85)")
    args = parser.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[Error] Could not open video source '{args.source}'.")
        sys.exit(1)

    detector = TongueDetector()
    mouse_controller = TongueMouseController(sensitivity=args.sensitivity, smoothing=0.18, enable_double_click=True)
    hud_renderer = MinimalHUD()

    window_name = "Tongue Mouse Pointer Controller"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    print("=" * 60)
    print("MINIMAL BLACK DARK MODE TONGUE MOUSE CONTROLLER")
    print(f"Sensitivity: {args.sensitivity} | Screen Resolution: {SCREEN_WIDTH} x {SCREEN_HEIGHT}")
    print("Controls:")
    print("  1. Move tongue tip -> Move OS mouse cursor smoothly")
    print("  2. Close mouth -> Triggers DOUBLE CLICK at locked tongue position!")
    print("  3. Press 'Q' or ESC -> Exit application")
    print("=" * 60)

    prev_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if isinstance(source, int):
                frame = cv2.flip(frame, 1)

            fh, fw, _ = frame.shape
            curr_time = time.time()
            fps = 1.0 / max(1e-5, curr_time - prev_time)
            prev_time = curr_time

            res = detector.process_frame(frame)
            mouse_info = mouse_controller.process_mouse_control(res, fw, fh)

            hud_frame = hud_renderer.draw_hud(frame, res, fps, mouse_mode=True, mouse_info=mouse_info)
            cv2.imshow(window_name, hud_frame)

            key = cv2.waitKey(1) & 0xFF
            if key in [ord('q'), ord('Q'), 27]:
                print("Exiting Tongue Mouse Controller...")
                break

    finally:
        detector.close()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
