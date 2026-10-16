import json
import requests
import logging
import uuid
import datetime
import asyncio
import websockets
import re
import os

from src.utils.weather_config import sensi_settings

LOG = logging.getLogger(__name__)

class SensiApi:
    def __init__(self, refresh_token):
        self._id = uuid.uuid4()
        self.status_code = 500
        self.access_token = None
        self.refresh_token = refresh_token
        self.expires_at = None
        self._websocket = None

    def _fleet(self):
        settings = sensi_settings()
        secret = os.getenv("SENSI_FLEET_CLIENT_SECRET", "").strip()
        if not secret:
            raise ValueError("SENSI_FLEET_CLIENT_SECRET is required")
        return settings, secret

    def request_tokens(self):
        if not self.refresh_token:
            raise ValueError("Refresh token not set. Pass it as a run parameter or set REFRESH_TOKEN in .env.")

        settings, secret = self._fleet()
        data = {
            "refresh_token": self.refresh_token,
            "client_id": settings["client_id"],
            "client_secret": secret,
            "grant_type": "refresh_token"
        }
        try:
            response = requests.post(settings["oauth_url"], data=data, headers={'rcs': settings["client_id"], 'rcf': '1'})
            response.raise_for_status()
            json_resp = response.json()
            self.access_token = json_resp.get("access_token")
            self.refresh_token = json_resp.get("refresh_token")
            self.expires_at = datetime.datetime.now() + datetime.timedelta(seconds=json_resp.get("expires_in") - 1800)
            self.status_code = response.status_code
            LOG.info("Tokens refreshed successfully.")
        except requests.RequestException as e:
            LOG.error(f"Token request failed: {e}")
            self.status_code = 500
            raise

    async def _connect(self, callback):
        headers = {"Authorization": f"Bearer {self.access_token}"}
        settings, _secret = self._fleet()
        try:
            async with websockets.connect(settings["ws_url"], extra_headers=headers, ping_interval=30, ping_timeout=60) as websocket:
                self._websocket = websocket
                asyncio.create_task(self._keep_alive())
                while True:
                    if self.expires_at < datetime.datetime.now():
                        LOG.info("Token expired, refreshing...")
                        break
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=60)
                        await self.process_response(response, callback)
                    except asyncio.TimeoutError:
                        LOG.warning("WebSocket recv timeout.")
                    except websockets.ConnectionClosed:
                        LOG.info("WebSocket closed.")
                        break
        except Exception as e:
            LOG.error(f"WebSocket connection error: {e}")

    async def _keep_alive(self):
        while True:
            await asyncio.sleep(30)
            if self._websocket:
                await self._websocket.send("40")

    def start(self, callback):
        while True:
            self.request_tokens()
            asyncio.run(self._connect(callback))
            LOG.info("Reconnecting after delay...")
            asyncio.sleep(10)  # Backoff to prevent rapid looping

    def send(self, request_json):
        if self._websocket:
            asyncio.create_task(self._websocket.send(f"421{json.dumps(request_json)}"))

    async def process_response(self, response, callback):
        parsed_response = self.parse_response(response)
        await callback(self, parsed_response)

    def parse_response(self, response):
        match = re.match(r'^(\d+)(.*)$', response)
        if match:
            response_type = match.group(1)
            json_str = match.group(2)
            try:
                parsed_json = json.loads(json_str) if json_str else None
                return response_type, parsed_json
            except json.JSONDecodeError:
                LOG.error(f"Invalid JSON in response: {response}")
        return None, None