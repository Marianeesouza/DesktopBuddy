import pygetwindow as gw
import psutil
import time

def test_get_window_title():
    # Get the title of the currently active window
    while True:
        last_title = ""
        active_window = gw.getActiveWindow()
        if active_window is not None:
            title = active_window.title
            if title != last_title:
                print(f"Active window title: {title}")
                last_title = title
        else:
            print("No active window found.")
        # Wait for a short period before checking again
        time.sleep(1)



if __name__ == "__main__":
    test_get_window_title()