import io
import datetime
from playwright.sync_api import sync_playwright
from PIL import Image, ImageOps

# Configuration for Kindle Oasis 2
TARGET_SIZE = (1264, 1680)

def capture_dashboard(url):
    """
    Captures a screenshot of the dashboard page using Playwright.
    Returns:
        bytes: The screenshot image data in PNG format.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Kindle Oasis 2 resolution is 1680x1264, but we display it rotated.
        # The User's CSS has width: 1680px; height: 1264px; (Landscape)
        # We need to capture it as is.
        page = browser.new_page(viewport={"width": 1680, "height": 1264})
        
        try:
            page.goto(url, wait_until="networkidle")
            # Extra wait to ensure all JS rendering (charts, etc) is done if networkidle isn't enough
            # page.wait_for_timeout(2000) 
            
            screenshot_bytes = page.screenshot(type="png")
            return screenshot_bytes
        except Exception as e:
            print(f"Error capturing screenshot: {e}")
            raise
        finally:
            browser.close()

def process_image_for_kindle(input_bytes):
    """
    Processes the raw screenshot for Kindle Oasis 2 display.
    Apply resizing (if needed), rotation (if needed), grayscale, and dithering.
    
    The user's request says: "1680*1264" and the CSS is landscape.
    Kindle typically renders portrait. 
    If the user holds the Kindle sideways, we just need to ensure the image is 1680x1264 or 1264x1680.
    
    The User's sample code has: target_size=(1264, 1680) but in their prompt they ask for "1680*1264".
    Wait, the User's CSS in initial_plan.md says:
            width: 1680px;
            height: 1264px;
    And the user says "Horizontal secondary screen".
    So the image should be 1680x1264.
    
    However, the User's provided python code `convert_for_oasis_fixed` has `target_size=(1264, 1680)`.
    And it does `ImageOps.fit`.
    
    If the screen is physical 1264x1680 (Portrait), and user wants Landscape content:
    We should probably render at 1680x1264, then rotate 90 degrees?
    
    Let's look at the User's code again:
    `img_fitted = ImageOps.fit(img, target_size, ...)` where target_size=(1264, 1680).
    
    But if the dashboard is designed as 1680 width, fitting it into 1264 width will squash it or crop it if we don't rotate.
    
    Let's assume the user handles rotation on the device or the device is just natively landscape (some older Kindles or hacked ones might render landscape). 
    BUT, commonly, to update the framebuffer, you send a file that matches the framebuffer dimensions.
    Oasis 2 is 1264 x 1680 natively.
    
    If I send a 1680x1264 image to a 1264x1680 screen, it will look wrong unless rotated.
    
    Let's follow the User's `initial_plan.md` which says:
    "Kindle Oasis 2 的 7 英寸屏幕（1680x1264 像素...）横向放置"
    And "CSS ... width: 1680px; height: 1264px;"
    
    So the HTML render is 1680x1264.
    If I produce a PNG that is 1680x1264, and the user's script `convert_for_oasis_fixed` sets `target_size=(1264, 1680)`, they might be conflicting.
    
    However, the USER's prompt says: "High quality render and return a 1680*1264 png image".
    So I should output 1680x1264.
    
    I will stick to the requested output dimension: 1680x1264.
    I will reuse the specific palette logic provided by the user.
    """
    
    try:
        img = Image.open(io.BytesIO(input_bytes))
        
        # 1. Force RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # 2. Resize/Fit
        # The user requested 1680x1264 specifically in the prompt.
        # The user's sample code used (1264, 1680) which might be for portrait.
        # Since the Dashboard is designed as Landscape 1680x1264, we keep it as is.
        # If the screenshot is already 1680x1264, ImageOps.fit is redundant but safe.
        target_size = (1680, 1264)
        img_fitted = ImageOps.fit(
            img, 
            target_size, 
            method=Image.Resampling.LANCZOS, 
            centering=(0.5, 0.5)
        )

        # 3. 16-color Grayscale Palette
        palette_img = Image.new('P', (1, 1))
        palette_data = []
        for i in range(16):
            val = int(i * 255 / 15)
            palette_data.extend((val, val, val))
        
        palette_data.extend([0] * (768 - len(palette_data)))
        palette_img.putpalette(palette_data)

        # 4. Quantize + Dither
        img_dithered_p = img_fitted.quantize(
            palette=palette_img, 
            dither=Image.Dither.FLOYDSTEINBERG
        )

        # 5. Convert back to 'L'
        final_img = img_dithered_p.convert('L')

        # 6. Save to bytes
        output = io.BytesIO()
        final_img.save(output, format="PNG", optimize=True)
        output.seek(0)
        return output

    except Exception as e:
        print(f"Error processing image: {e}")
        import traceback
        traceback.print_exc()
        raise

def render_dashboard_to_bytes(url):
    """
    Full pipeline: Capture -> Process -> Return Bytes
    """
    start_time = datetime.datetime.now()
    print(f"[{start_time}] Starting Render Job for {url}")
    
    raw_png = capture_dashboard(url)
    processed_png_io = process_image_for_kindle(raw_png)
    
    end_time = datetime.datetime.now()
    print(f"[{end_time}] Render finished in {(end_time - start_time).total_seconds()}s")
    
    return processed_png_io
