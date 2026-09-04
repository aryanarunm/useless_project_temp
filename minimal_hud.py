import os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

# Try loading Windows system fonts (Segoe UI / Montserrat equivalent)
FONT_PATH = "C:\\Windows\\Fonts\\segoeui.ttf"
FONT_BOLD_PATH = "C:\\Windows\\Fonts\\segoeuib.ttf"

def get_pil_font(size=18, bold=False):
    path = FONT_BOLD_PATH if bold else FONT_PATH
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

class MinimalHUD:
    """
    Ultra-clean, minimal pitch-black dark mode overlay system with Montserrat-style typography.
    """
    def __init__(self):
        self.font_sm = get_pil_font(14, bold=False)
        self.font_md = get_pil_font(18, bold=True)
        self.font_lg = get_pil_font(22, bold=True)

    def draw_hud(self, frame_bgr, detection_res, fps, mouse_mode=True, mouse_info=None):
        h, w, _ = frame_bgr.shape

        # Pitch Black Matte Header Card (Top 90px)
        overlay = frame_bgr.copy()
        cv2.rectangle(overlay, (16, 16), (w - 16, 96), (10, 11, 14), -1) # #0a0b0e
        cv2.addWeighted(overlay, 0.88, frame_bgr, 0.12, 0, frame_bgr)

        # Thin sleek card border
        cv2.rectangle(frame_bgr, (16, 16), (w - 16, 96), (35, 38, 48), 1)

        # Convert to PIL RGB image for Montserrat typography
        rgb_img = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)
        draw = ImageDraw.Draw(pil_img)

        # Mode Pill Badge: MOUSE CONTROL
        badge_text = "MOUSE CONTROL"
        badge_bg = (16, 185, 129)  # Emerald #10b981
        badge_fg = (10, 11, 14)

        draw.rounded_rectangle([32, 28, 160, 52], radius=12, fill=badge_bg)
        draw.text((44, 32), badge_text, font=self.font_sm, fill=badge_fg)

        # Title Text & FPS
        draw.text((176, 30), "Tongue Mouse Pointer System", font=self.font_md, fill=(249, 250, 251))
        draw.text((w - 120, 32), f"FPS  {fps:.1f}", font=self.font_sm, fill=(156, 163, 175))

        # Mouse Telemetry
        if mouse_info:
            cur_x, cur_y = mouse_info.get('mouse_x', 0), mouse_info.get('mouse_y', 0)
            act = mouse_info.get('click_event', '')
            content_str = f"Cursor  ({cur_x}, {cur_y})"
            if act:
                content_str += f"   •   {act}"
                # Draw minimal click notification badge in center of screen
                draw.rounded_rectangle([w // 2 - 160, h // 2 - 25, w // 2 + 160, h // 2 + 25], radius=16, fill=(16, 185, 129))
                draw.text((w // 2 - 130, h // 2 - 12), f"LOCKED {act}", font=self.font_lg, fill=(10, 11, 14))
            else:
                content_str += "   •   Open mouth to move cursor  |  Close mouth to double-click"
            
            draw.text((32, 64), content_str, font=self.font_sm, fill=(156, 163, 175))

        # Minimal Footer Pill
        draw.text((32, h - 30), "[Q] Exit Mouse Controller", font=self.font_sm, fill=(156, 163, 175))

        # Convert PIL back to BGR OpenCV
        frame_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # Minimal Target Reticle (Subtle mint dot with thin aura)
        if detection_res.get('smoothed_tip'):
            tx, ty = detection_res['smoothed_tip']
            cv2.circle(frame_bgr, (tx, ty), 4, (129, 185, 16), -1, cv2.LINE_AA) # BGR
            cv2.circle(frame_bgr, (tx, ty), 10, (129, 185, 16), 1, cv2.LINE_AA)

        return frame_bgr
