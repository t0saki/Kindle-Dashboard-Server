import requests
from PIL import Image
import io

from config import Config

def test_render():
    url = f"http://127.0.0.1:{Config.PORT}/render"
    print(f"Requesting {url}...")
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            print("Success! Status 200.")
            content_type = r.headers.get('Content-Type')
            print(f"Content-Type: {content_type}")
            
            img = Image.open(io.BytesIO(r.content))
            print(f"Image Size: {img.size}")
            print(f"Image Mode: {img.mode}")
            
            if img.size == (Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT):
                print(f"PASS: Size is {Config.SCREEN_WIDTH}x{Config.SCREEN_HEIGHT}")
            else:
                print(f"FAIL: Size mismatch {img.size}")
                
            if img.mode == 'L':
                print("PASS: Mode is L (Grayscale)")
            else:
                 print(f"FAIL: Mode is {img.mode}")
                 
            # Save for manual inspection if needed
            with open("test_output_dashboard.png", "wb") as f:
                f.write(r.content)
                print("Saved to test_output_dashboard.png")
                
        else:
            print(f"Error: Status {r.status_code}")
            print(r.text)
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_render()
