import time
from tongue_mouse_controller import TongueMouseController

def test_mouse_controller():
    print("=" * 60)
    print("TESTING TONGUE MOUSE CONTROLLER (DOUBLE CLICK ON CLOSE)")
    print("=" * 60)

    controller = TongueMouseController(sensitivity=0.85, smoothing=0.18, enable_double_click=True)
    frame_w, frame_h = 640, 480

    # 1. Open mouth & track tongue at (320, 240)
    res_open1 = {'mouth_open': True, 'mouth_ratio': 0.09, 'smoothed_tip': (320, 240)}
    info1 = controller.process_mouse_control(res_open1, frame_w, frame_h)
    print(f"[Test 1 - Center Open Mouth] Mouse Position: ({info1['mouse_x']}, {info1['mouse_y']})")

    # 2. Move tongue to target position (380, 200)
    res_open2 = {'mouth_open': True, 'mouth_ratio': 0.09, 'smoothed_tip': (380, 200)}
    info2 = controller.process_mouse_control(res_open2, frame_w, frame_h)
    last_x, last_y = info2['mouse_x'], info2['mouse_y']
    print(f"[Test 2 - Pointing Target Position] Mouse Position: ({last_x}, {last_y})")

    # 3. Start closing mouth (transitional frame) -> Position Locked
    res_trans = {'mouth_open': True, 'mouth_ratio': 0.055, 'smoothed_tip': (390, 170)}
    info_trans = controller.process_mouse_control(res_trans, frame_w, frame_h)
    print(f"[Test 3 - Transitional Closing] Mouse Position Locked at: ({info_trans['mouse_x']}, {info_trans['mouse_y']})")
    assert (info_trans['mouse_x'], info_trans['mouse_y']) == (last_x, last_y), "Cursor must remain locked at last stable tongue position!"

    # 4. Mouth fully closed -> Trigger Double Click at locked position
    res_closed = {'mouth_open': False, 'mouth_ratio': 0.03, 'smoothed_tip': None}
    info_click = controller.process_mouse_control(res_closed, frame_w, frame_h)
    print(f"[Test 4 - Double Click Executed] Action: '{info_click['click_event']}' at ({info_click['mouse_x']}, {info_click['mouse_y']})")
    assert info_click['click_event'] == "DOUBLE CLICK", "Expected DOUBLE CLICK event"
    assert (info_click['mouse_x'], info_click['mouse_y']) == (last_x, last_y), "Double click must be executed at exact locked tongue position!"

    print("=" * 60)
    print("DOUBLE CLICK & POSITION LOCKING TEST COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == '__main__':
    test_mouse_controller()
