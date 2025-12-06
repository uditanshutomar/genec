"""
WebSocket progress server for real-time communication with VS Code extension.

Provides bidirectional real-time progress updates instead of parsing stderr.
"""

import asyncio
import json
import threading
from typing import Callable, Optional

from genec.utils.logging_utils import get_logger


class ProgressServer:
    """WebSocket server for real-time progress updates."""
    
    def __init__(self, port: int = 9876):
        """
        Initialize progress server.
        
        Args:
            port: Port to listen on (default: 9876)
        """
        self.port = port
        self.logger = get_logger(self.__class__.__name__)
        self._clients: set = set()
        self._server = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
    
    def start(self):
        """Start the WebSocket server in a background thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        self.logger.info(f"WebSocket progress server starting on port {self.port}")
    
    def stop(self):
        """Stop the WebSocket server."""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2)
        self.logger.info("WebSocket progress server stopped")
    
    def _run_server(self):
        """Run server in background thread."""
        try:
            import websockets
        except ImportError:
            self.logger.warning(
                "websockets library not installed. "
                "Install with: pip install websockets"
            )
            return
        
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        async def handler(websocket):
            self._clients.add(websocket)
            self.logger.debug(f"Client connected: {websocket.remote_address}")
            try:
                # Keep connection alive
                async for message in websocket:
                    # Handle incoming messages (e.g., cancel requests)
                    try:
                        data = json.loads(message)
                        if data.get("type") == "cancel":
                            self.logger.info("Cancel request received from client")
                            # Handle cancellation through callback if set
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass
            finally:
                self._clients.discard(websocket)
                self.logger.debug("Client disconnected")
        
        async def serve():
            async with websockets.serve(handler, "localhost", self.port):
                while self._running:
                    await asyncio.sleep(0.1)
        
        try:
            self._loop.run_until_complete(serve())
        except Exception as e:
            self.logger.debug(f"Server stopped: {e}")
    
    def emit_progress(
        self,
        stage: int,
        total: int,
        message: str,
        details: Optional[dict] = None
    ):
        """
        Emit progress event to all connected clients.
        
        Args:
            stage: Current stage number (0-indexed)
            total: Total number of stages
            message: Human-readable progress message
            details: Optional additional data
        """
        event = {
            "type": "progress",
            "stage": stage,
            "total": total,
            "percent": int((stage / total) * 100) if total > 0 else 0,
            "message": message,
        }
        if details:
            event["details"] = details
        
        self._broadcast(event)
    
    def emit_error(self, error: str, details: Optional[dict] = None):
        """Emit error event to all connected clients."""
        event = {"type": "error", "message": error}
        if details:
            event["details"] = details
        self._broadcast(event)
    
    def emit_complete(self, result: dict):
        """Emit completion event with results."""
        event = {"type": "complete", "result": result}
        self._broadcast(event)
    
    def _broadcast(self, event: dict):
        """Broadcast event to all connected clients."""
        if not self._clients:
            return
        
        message = json.dumps(event)
        
        if self._loop:
            async def send_all():
                for client in list(self._clients):
                    try:
                        await client.send(message)
                    except Exception:
                        self._clients.discard(client)
            
            asyncio.run_coroutine_threadsafe(send_all(), self._loop)


# Global singleton for easy access from pipeline
_progress_server: Optional[ProgressServer] = None


def get_progress_server(port: int = 9876) -> ProgressServer:
    """Get or create the global progress server instance."""
    global _progress_server
    if _progress_server is None:
        _progress_server = ProgressServer(port)
    return _progress_server


def emit_progress(stage: int, total: int, message: str, details: Optional[dict] = None):
    """Convenience function to emit progress if server is running."""
    if _progress_server and _progress_server._running:
        _progress_server.emit_progress(stage, total, message, details)
