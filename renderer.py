import io
import datetime
from playwright.sync_api import sync_playwright
from PIL import Image, ImageOps
from config import Config


def capture_dashboard(url):
    """
    Captures a screenshot of the dashboard page using Playwright.
    Returns:
        bytes: The screenshot image data in PNG format.
    """
    # Define the design resolution that matches the CSS/HTML layout
    DESIGN_WIDTH = 1680
    DESIGN_HEIGHT = 1264

    # Calculate scale factor based on target screen width versus design width
    # We assume aspect ratio is reasonably preserved or handled by the user's config
    # but strictly speaking, we scale based on width to ensure full width fit.
    # If the user has a different aspect ratio, we might have vertical space issues,
    # but the primary constraint is width.
    scale_factor = Config.SCREEN_WIDTH / DESIGN_WIDTH

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # We set the viewport to the DESIGN resolution so the CSS layout remains identical.
        # We set device_scale_factor so the browser renders at a higher/lower resolution
        # effectively scaling the output image to (DESIGN_WIDTH * scale) x (DESIGN_HEIGHT * scale).
        page = browser.new_page(
            viewport={"width": DESIGN_WIDTH, "height": DESIGN_HEIGHT},
            device_scale_factor=scale_factor
        )
        
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
    """
    
    try:
        img = Image.open(io.BytesIO(input_bytes))
        
        # 1. Force RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # 2. Resize/Fit
        # We use the configured screen resolution as the target size.
        target_size = (Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT)
        
        # Optimization: If the image is already at the target size (or very close), skip heavy resizing
        # The browser capture should be exact, but we check to be safe.
        if img.size == target_size:
            img_fitted = img
        else:
            # Fallback to Resize/Fit if dimensions don't match exactly
            # This handles cases where scale factor rounding or other issues might cause slight off-by-one
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

