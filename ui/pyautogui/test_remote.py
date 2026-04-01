import time
from client import get_screenshot, send_action

def main():
    print("--- Starting Remote Control Full Test ---")
    
    # 1. Capture and save screenshot
    print("\n[Test 1] Capturing and saving remote screenshot...")
    get_screenshot(save_path="test_capture.png")
    
    # Add a small delay so you can verify the image was saved
    time.sleep(1)
    
    # 2. Execute a visibly slow mouse movement block on the server machine
    print("\n[Test 2] Executing visible mouse movement...")
    visible_movement_code = """
import pyautogui
print("Executing remote macro...")
# A slow 200x200 square
distance = 200
duration = 0.5
pyautogui.moveRel(distance, 0, duration=duration)    # Right
pyautogui.moveRel(0, distance, duration=duration)    # Down
pyautogui.moveRel(-distance, 0, duration=duration)   # Left
pyautogui.moveRel(0, -distance, duration=duration)   # Up
print("Macro complete!")
"""
    send_action(visible_movement_code)
    
    print("\n--- Test Finished ---")

if __name__ == "__main__":
    main()
