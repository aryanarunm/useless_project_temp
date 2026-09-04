<img width="1280" height="640" alt="git (1)" src="https://github.com/user-attachments/assets/8920b256-2ba8-4988-b824-5351134eb4bd" />

# Tongue Pointer 👅🖱️

## Basic Details
### Team Name: TongueTech

### Team Members
- Team Lead: Aryan - MITS

### Project Description
Real-time tongue tip tracking interface using computer vision (MediaPipe + OpenCV) that allows hands-free control of your operating system mouse cursor and triggers double-clicks when you close your mouth.

### The Problem (that doesn't exist)
Using your hands to move a mouse is way too conventional. Why use fingers when your tongue can navigate Windows, open applications, and execute native double-clicks without touching any hardware?

### The Solution (that nobody asked for)
A non-contact vision algorithm tracking tongue movements in real-time, mapping sub-pixel displacement to native Windows `User32` cursor coordinates, featuring position locking and double-click triggers on mouth closure!

## Technical Details
### Technologies/Components Used
For Software:
- Python 3.13
- OpenCV 4.8+
- MediaPipe 0.10+ (FaceLandmarker 468 3D Landmarks)
- NumPy
- Pillow (PIL)
- Windows User32 Native CTypes API

### Implementation
For Software:
# Installation
```bash
pip install -r requirements.txt
```

# Run Unit Tests
```bash
python test_mouse_controller.py
```

# Run Application
```bash
python tongue_mouse_controller.py
```

### Project Controls & Features
- **Tongue Tip Movement**: Smoothly moves OS mouse cursor across your full screen.
- **Position Locking**: Freezes cursor coordinates when closing mouth to eliminate jump/wobble.
- **Double Click Execution**: Closing mouth automatically executes a native Windows double-click.
- **Minimal Pitch-Black HUD**: Dark mode overlay (`#0a0b0e`) with real-time FPS counter and target reticle.

---
Made with ❤️ at TinkerHub Useless Projects 

![Static Badge](https://img.shields.io/badge/TinkerHub-24?color=%23000000&link=https%3A%2F%2Fwww.tinkerhub.org%2F)
![Static Badge](https://img.shields.io/badge/UselessProjects--26-26?link=https%3A%2F%2Ftinkerhub.org%2Fevents%2F1M8ORET9A1%2Fuseless-projects-3.0)



