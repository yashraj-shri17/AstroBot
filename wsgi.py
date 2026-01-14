from main_App import app
from waitress import serve
import os
import logging

if __name__ == "__main__":
    # Ensure logs directory exists
    if not os.path.exists('logs'):
        os.mkdir('logs')
        
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
    logger = logging.getLogger('waitress')
    
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    
    logger.info(f"Starting AstroBot on {host}:{port}")
    serve(app, host=host, port=port)
