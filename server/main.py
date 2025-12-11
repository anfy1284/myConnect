import asyncio
import websockets
import json
import logging
import os
from datetime import datetime, timedelta

# Load configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

def load_config():
    # Try loading from file first
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    
    # If file not found, try environment variables (for Koyeb/Docker)
    print("Config file not found, checking environment variables...")
    
    clients_env = os.environ.get('CLIENTS_JSON')
    if not clients_env:
        print("Error: CLIENTS_JSON environment variable not set.")
        return None
        
    try:
        clients = json.loads(clients_env)
    except json.JSONDecodeError:
        print("Error: CLIENTS_JSON is not valid JSON.")
        return None

    return {
        "host": "0.0.0.0",
        "port": int(os.environ.get('PORT', 8000)),
        "clients": clients,
        "request_timeout": int(os.environ.get('REQUEST_TIMEOUT', 30)),
        "log_retention_days": int(os.environ.get('LOG_RETENTION_DAYS', 7)),
        "enable_logging": os.environ.get('ENABLE_LOGGING', 'True').lower() == 'true',
        "log_file": "server.log" # Usually stdout is better for cloud, but keeping file for now
    }

config = load_config()

# Setup logging
if config:
    # For cloud deployment, we often prefer logging to stdout
    if os.environ.get('LOG_TO_STDOUT', 'False').lower() == 'true':
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
    elif config.get('enable_logging', True):
        logging.basicConfig(
            filename=config.get('log_file', 'server.log'),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(level=logging.CRITICAL)
else:
    # Fallback if config failed
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Store connected clients: {client_name: websocket}
connected_clients = {}

async def cleanup_logs():
    """Periodically clean up old logs."""
    while True:
        try:
            retention_days = config.get('log_retention_days', 7)
            log_file = config.get('log_file', 'server.log')
            if os.path.exists(log_file):
                # This is a simple implementation. For a real production system, 
                # log rotation (logging.handlers.RotatingFileHandler) is better.
                # Here we just check file modification time for simplicity or skip if complex.
                # A proper cleanup would involve parsing the log or rotating it.
                # Let's stick to standard logging rotation in a real scenario, 
                # but for this script, we'll just log that we are "cleaning" (placeholder).
                pass
        except Exception as e:
            logger.error(f"Error cleaning logs: {e}")
        await asyncio.sleep(86400) # Run once a day

async def handler(websocket):
    client_id = None
    try:
        # Authentication handshake
        # Client sends: {"token": "...", "name": "..."}
        auth_msg = await asyncio.wait_for(websocket.recv(), timeout=10)
        auth_data = json.loads(auth_msg)
        token = auth_data.get('token')
        name = auth_data.get('name')

        expected_name = config['clients'].get(token)
        
        if not expected_name:
            logger.warning(f"Invalid token attempt: {token}")
            await websocket.close(code=4001, reason="Invalid token")
            return

        if expected_name != name:
             logger.warning(f"Token/Name mismatch. Token maps to {expected_name}, got {name}")
             await websocket.close(code=4002, reason="Name mismatch")
             return

        client_id = name
        connected_clients[client_id] = websocket
        logger.info(f"Client connected: {client_id}")
        await websocket.send(json.dumps({"status": "authenticated"}))

        async for message in websocket:
            # Message format: {"target": "target_client_name", "type": "...", "payload": "..."}
            try:
                data = json.loads(message)
                target = data.get('target')
                
                if target and target in connected_clients:
                    target_ws = connected_clients[target]
                    # Forward the message
                    # We might want to wrap it or just pass it through
                    # Adding sender info might be useful
                    data['sender'] = client_id
                    await target_ws.send(json.dumps(data))
                    logger.info(f"Relayed message from {client_id} to {target}")
                else:
                    error_msg = {"type": "error", "message": f"Target {target} not found"}
                    await websocket.send(json.dumps(error_msg))
                    logger.warning(f"Client {client_id} tried to send to unknown target {target}")

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from {client_id}")
            except Exception as e:
                logger.error(f"Error processing message from {client_id}: {e}")

    except asyncio.TimeoutError:
        logger.warning("Authentication timeout")
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Connection closed: {client_id}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if client_id and client_id in connected_clients:
            del connected_clients[client_id]
            logger.info(f"Client disconnected: {client_id}")

async def process_request(connection, request):
    """
    Handle HTTP requests for health checks.
    """
    if request.path == "/health":
        return (200, [("Content-Type", "text/plain")], b"OK")
    return None

async def main():
    if not config:
        return

    host = config.get('host', '0.0.0.0')
    port = config.get('port', 8765)
    
    ssl_context = None
    if config.get('use_tls'):
        import ssl
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cert_file = config.get('cert_file')
        key_file = config.get('key_file')
        if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
            ssl_context.load_cert_chain(cert_file, key_file)
            logger.info("TLS enabled")
        else:
            logger.error("TLS configured but cert/key files missing")
            return

    logger.info(f"Starting server on {host}:{port}")
    
    # Start log cleanup task
    asyncio.create_task(cleanup_logs())

    async with websockets.serve(handler, host, port, ssl=ssl_context, process_request=process_request):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
