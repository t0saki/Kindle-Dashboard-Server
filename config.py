import os
import ast

def load_dotenv(path=".env"):
    """
    Simple .env loader to avoid adding python-dotenv dependency.
    Does not override existing environment variables.
    """
    if not os.path.exists(path):
        return
    
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                
                if key and key not in os.environ:
                    os.environ[key] = value

# Load environment variables from .env file
load_dotenv()

class Config:
    # --- Server Configuration ---
    # Note: Port/Host are often handled by the WSGI server or docker-compose, 
    # but good to have defaults here.
    PORT = int(os.environ.get("PORT", 5000))
    HOST = os.environ.get("HOST", "0.0.0.0")

    # --- Location Configuration ---
    LATITUDE = float(os.environ.get("LATITUDE", "1.27710"))
    LONGITUDE = float(os.environ.get("LONGITUDE", "103.84610"))
    CITY_NAME = os.environ.get("CITY_NAME", "Singapore") # Used for display if location lookup fails or is disabled
    TIMEZONE = os.environ.get("TIMEZONE", "Asia/Singapore")

    # --- Screen Configuration ---
    SCREEN_WIDTH = int(os.environ.get("SCREEN_WIDTH", 1680))
    SCREEN_HEIGHT = int(os.environ.get("SCREEN_HEIGHT", 1264))

    # --- Locale & Localization ---
    LANGUAGE = os.environ.get("LANGUAGE", "CN") # CN or EN
    HOLIDAY_COUNTRY = os.environ.get("HOLIDAY_COUNTRY", "SG") # Country code for `holidays` library
    
    # --- Cache Durations (in seconds) ---
    CACHE_TTL_WEATHER = int(os.environ.get("CACHE_TTL_WEATHER", 600))     # 10 minutes
    CACHE_TTL_FINANCE = int(os.environ.get("CACHE_TTL_FINANCE", 900))     # 15 minutes
    CACHE_TTL_NEWS = int(os.environ.get("CACHE_TTL_NEWS", 300))           # 5 minutes
    CACHE_TTL_RENDER = int(os.environ.get("CACHE_TTL_RENDER", 60))        # 1 minute

    # --- Finance Configuration ---
    # Expected format: JSON list of dicts or just a comma-separated list of symbols for defaults
    # If using formatted string in env: '[{"symbol": "SGDCNY=X", "name": "SGD/CNY"}, ...]'
    # OR simple comma separated: "SGDCNY=X,BTC-USD" (will use symbol as name)
    FINANCE_TICKERS_RAW = os.environ.get("FINANCE_TICKERS", 
        '[{"symbol": "SGDCNY=X", "name": "SGD/CNY"}, {"symbol": "CNY=X", "name": "USD/CNY"}, {"symbol": "BTC-USD", "name": "BTC/USD"}]'
    )
    
    @staticmethod
    def get_finance_tickers():
        raw = Config.FINANCE_TICKERS_RAW
        try:
            # Try parsing as JSON first
            return ast.literal_eval(raw)
        except:
            # Fallback to comma-separated list
            return [{"symbol": s.strip(), "name": s.strip()} for s in raw.split(",") if s.strip()]

    # --- Work/Commute Logic ---
    WORK_START_HOUR = int(os.environ.get("WORK_START_HOUR", 10))
    WORK_END_HOUR = int(os.environ.get("WORK_END_HOUR", 18))
