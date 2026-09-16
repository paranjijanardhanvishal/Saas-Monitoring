import os
import sys
import logging
from mitmproxy.tools.main import mitmdump

# Add the project root to the python path so mitmproxy can import 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_proxy():
    proxy_host = os.environ.get("PROXY_HOST", "127.0.0.1")
    proxy_port = os.environ.get("PROXY_PORT", "8080")
    
    script_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backend", "app", "proxy", "monitor.py"
    )
    
    logger.info(f"Starting API Monitoring Proxy on {proxy_host}:{proxy_port}...")
    logger.info(f"Loading mitmproxy script: {script_path}")
    
    # Run mitmdump programmatically
    sys.argv = [
        "mitmdump",
        "-s", script_path,
        "--listen-host", proxy_host,
        "--listen-port", proxy_port,
        "--set", "block_global=false"
    ]
    
    mitmdump()

if __name__ == "__main__":
    run_proxy()
