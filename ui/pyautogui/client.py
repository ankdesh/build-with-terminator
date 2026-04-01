import requests

SERVER_URL = "http://localhost:8000"

def get_screenshot(save_path: str | None = None):
    print("Requesting screenshot from server...")
    try:
        response = requests.get(f"{SERVER_URL}/screenshot")
        response.raise_for_status()
        
        if save_path:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            print(f"Saved screenshot to {save_path}")
        else:
            print(f"Received screenshot data ({len(response.content)} bytes).")
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Failed to get screenshot:\n{e}")
        return None

def send_action(python_code: str):
    print(f"Sending python code to execute at {SERVER_URL}/action...")
    try:
        response = requests.post(
            f"{SERVER_URL}/action",
            json={"code": python_code}
        )
        if response.status_code == 200:
            print(f"Success: {response.json()}")
        else:
            print(f"Error ({response.status_code}): {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send action:\n{e}")

if __name__ == "__main__":
    # 1. Test Screenshot logic
    get_screenshot()
    print("-" * 40)

    # 2. Test Remote UI Action
    # This snippet moves the mouse relative to its current position
    # The user can customize this payload.
    # NOTE: Since this executes on the remote machine (server), any mouse 
    # move will happen there.
    sample_code = """
import pyautogui
# Moving mouse safely
pyautogui.moveRel(10, 0, duration=0.2)
print("Remote action completed successfully!")
"""
    send_action(sample_code)
