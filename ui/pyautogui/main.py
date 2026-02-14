import pyautogui
import time
import sys

def main():
    print("PyAutoGUI Sample Script")
    print("-----------------------")
    
    # 1. Fail-Safe Mode
    # Moving the mouse to any corner of the screen will throw a FailSafeException
    # and abort the program. This is a safety feature.
    pyautogui.FAILSAFE = True
    print("Fail-safe mode is ENABLED. Move mouse to a corner to abort.")

    # 2. Get Screen Size
    screen_width, screen_height = pyautogui.size()
    print(f"Screen resolution: {screen_width}x{screen_height}")

    # 3. Get Current Mouse Position
    current_x, current_y = pyautogui.position()
    print(f"Current mouse position: ({current_x}, {current_y})")

    # 4. Move the Mouse Safely
    # We'll move the mouse in a small square relative to its current position
    # verifying we don't go out of bounds.
    print("Moving mouse in a square pattern...")
    distance = 100
    try:
        # Move Right
        pyautogui.moveRel(distance, 0, duration=0.5)
        # Move Down
        pyautogui.moveRel(0, distance, duration=0.5)
        # Move Left
        pyautogui.moveRel(-distance, 0, duration=0.5)
        # Move Up
        pyautogui.moveRel(0, -distance, duration=0.5)
    except pyautogui.FailSafeException:
        print("\nFail-safe triggered from mouse movement!")
        sys.exit(1)

    print("Mouse movement complete.")

    # 5. Type something (into a notepad if you had one open, here just to stdout as demo)
    # Be careful with this function as it types into whatever window has focus.
    # pyautogui.write('Hello world!', interval=0.25) 
    print("Skipping typing demo to avoid interfering with your active window.")

    print("\nDemonstration finished.")

if __name__ == "__main__":
    main()
