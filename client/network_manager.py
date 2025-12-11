import asyncio
import websockets
import json
import logging
import pydivert
import threading
import time
from queue import Queue

logger = logging.getLogger(__name__)

class NetworkManager:
    def __init__(self, config, status_callback=None):
        self.config = config
        self.ws = None
        self.running = False
        self.packet_queue = None # Will be initialized in run_async_loop
        self.response_queue = Queue() # Thread-safe queue for WinDivert thread
        self.nat_table = {} # (src_ip, src_port) -> (original_src_ip, original_src_port) for proxy mode
        self.status_callback = status_callback
        
    async def connect_to_server(self):
        url = self.config.get('server_url')
        while self.running:
            try:
                if self.status_callback:
                    self.status_callback(False) # Connecting...
                    
                async with websockets.connect(url) as websocket:
                    self.ws = websocket
                    # Authenticate
                    auth_msg = {
                        "token": self.config.get('client_token'),
                        "name": self.config.get('client_name')
                    }
                    await websocket.send(json.dumps(auth_msg))
                    response = await websocket.recv()
                    logger.info(f"Server auth response: {response}")
                    
                    if self.status_callback:
                        self.status_callback(True) # Connected

                    # Start listener tasks
                    await asyncio.gather(
                        self.receive_handler(),
                        self.send_handler()
                    )
            except Exception as e:
                logger.error(f"Connection error: {e}")
                if self.status_callback:
                    self.status_callback(False) # Disconnected
                await asyncio.sleep(5) # Reconnect delay

    async def receive_handler(self):
        try:
            async for message in self.ws:
                data = json.loads(message)
                # Handle incoming packets from server (responses or requests to proxy)
                if data.get('type') == 'packet':
                    # This is a packet we need to inject
                    # It could be a response to our request, OR a request for us to proxy
                    self.handle_incoming_packet(data)
        except Exception as e:
            logger.error(f"Receive error: {e}")

    async def send_handler(self):
        while self.running:
            packet_data = await self.packet_queue.get()
            if self.ws:
                try:
                    await self.ws.send(json.dumps(packet_data))
                except Exception as e:
                    logger.error(f"Send error: {e}")
                    # Maybe put back in queue?

    def handle_incoming_packet(self, data):
        # This runs in asyncio loop, but WinDivert might be in another thread.
        # We need to inject this packet.
        # For simplicity, we can use a separate WinDivert handle for injection or share one if possible.
        # Or just use pydivert.WinDivert().send(packet) (creates new handle).
        
        payload = bytes.fromhex(data['payload'])
        # We need to determine if this is a response to US (Initiator) or a request FOR US (Executor)
        
        # Simplified logic:
        # If we are the target of the message, we process it.
        # The server routes messages.
        
        # If we are acting as Executor (Proxy), we receive a packet, we need to NAT it and send it out.
        # If we are Initiator, we receive a response packet, we need to de-NAT (if needed) and inject inbound.
        
        # Let's assume the payload is the raw IP packet.
        try:
            # We can't easily parse raw bytes to pydivert Packet without a handle context usually, 
            # but we can try to just inject it if we know direction.
            
            # However, pydivert.Packet takes raw data.
            # We need to know if it's inbound or outbound injection.
            
            # If we are Initiator receiving a response: It should be injected as INBOUND.
            # If we are Executor receiving a request: It should be injected as OUTBOUND.
            
            mode = data.get('mode') # 'response' or 'request'
            
            if mode == 'response':
                # We are Initiator, receiving response from Executor
                # Inject as INBOUND
                # We might need to fix checksums? pydivert does this automatically if we modify.
                # But here we just have bytes.
                
                # To inject, we can open a handle.
                with pydivert.WinDivert() as w:
                    w.send(pydivert.Packet(payload, interface=(pydivert.Packet.Network, pydivert.Packet.Inbound)))
                    
            elif mode == 'request':
                # We are Executor, receiving request from Initiator
                # Inject as OUTBOUND
                # But we need to NAT it first?
                # If we just inject outbound with original SrcIP, it might be dropped.
                # For this PoC, let's assume we just inject and see. 
                # Real NAT is complex.
                
                # Better approach for Executor:
                # 1. Parse packet.
                # 2. Change SrcIP to Me.
                # 3. Save mapping.
                # 4. Inject Outbound.
                pass 
                
        except Exception as e:
            logger.error(f"Injection error: {e}")

    def start(self):
        self.running = True
        # Start WebSocket thread
        self.ws_thread = threading.Thread(target=self.run_async_loop)
        self.ws_thread.start()
        
        # Start WinDivert thread
        self.wd_thread = threading.Thread(target=self.run_windivert)
        self.wd_thread.start()

    def run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.packet_queue = asyncio.Queue()
        self.loop.run_until_complete(self.connect_to_server())

    def run_windivert(self):
        # Build filter string
        filters = self.config.get('filters', [])
        if not filters:
            logger.info("No filters configured.")
            return

        filter_str = filters[0]['windivert_filter']
        target_client = filters[0]['target_client']
        
        # Support multiple keywords
        domain_keywords = filters[0].get('domain_keywords', [])
        if filters[0].get('domain_keyword'):
            domain_keywords.append(filters[0].get('domain_keyword'))
        
        logger.info(f"Starting WinDivert with filter: {filter_str}")
        
        # Track flows that should be diverted: set of (src_ip, src_port, dst_ip, dst_port)
        diverted_flows = set()
        # Track IPs that should be diverted (redirect all ports for these IPs)
        diverted_ips = set()

        try:
            self.w = pydivert.WinDivert(filter_str)
            with self.w as w:
                for packet in w:
                    if not self.running:
                        break
                    
                    should_divert = False
                    
                    # Drop UDP 443 (QUIC) to force TCP
                    if packet.udp and packet.dst_port == 443:
                        # logger.info("Dropping UDP 443 (QUIC) packet to force TCP")
                        continue # Drop packet (do not re-inject)

                    # Flow identification tuple
                    flow_id = (packet.src_addr, packet.src_port, packet.dst_addr, packet.dst_port)
                    dst_ip = packet.dst_addr

                    if domain_keywords:
                        # Check if this flow OR IP is already marked for diversion
                        if flow_id in diverted_flows or dst_ip in diverted_ips:
                            should_divert = True
                        else:
                            # Check payload for keyword (only for TCP usually)
                            try:
                                if packet.payload:
                                    # Debug: print first 100 bytes of payload to see SNI
                                    # logger.info(f"Payload: {packet.payload[:100]}")
                                    
                                    for kw in domain_keywords:
                                        if kw.encode() in packet.payload:
                                            logger.info(f"Found keyword '{kw}' in packet. Diverting IP {dst_ip}")
                                            diverted_flows.add(flow_id)
                                            diverted_ips.add(dst_ip)
                                            should_divert = True
                                            break
                            except Exception:
                                pass
                    else:
                        # No keyword filtering, divert everything matching the filter
                        should_divert = True

                    if should_divert:
                        # Serialize and queue for sending
                        payload = packet.raw.hex()
                        msg = {
                            "target": target_client,
                            "type": "packet",
                            "mode": "request", # We are requesting
                            "payload": payload
                        }
                        
                        # Schedule the put() in the asyncio loop
                        if hasattr(self, 'loop') and self.packet_queue is not None:
                            self.loop.call_soon_threadsafe(self.packet_queue.put_nowait, msg)
                        else:
                            logger.warning("Loop or queue not ready yet")
                    else:
                        # Not diverting, re-inject locally to let it pass to internet
                        w.send(packet)
                    
        except OSError as e:
            if e.winerror == 6 and not self.running:
                # Handle closed (normal shutdown)
                pass
            else:
                logger.error(f"WinDivert error: {e}")
        except Exception as e:
            logger.error(f"WinDivert error: {e}")

    def stop(self):
        self.running = False
        if hasattr(self, 'w'):
            try:
                self.w.close()
            except:
                pass
