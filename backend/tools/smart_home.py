"""
tools/smart_home.py — Home Assistant REST API integration.
"""

import logging
import os
import re
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

_HASS_URL = os.getenv("HASS_URL", "http://homeassistant.local:8123")
_HASS_TOKEN = os.getenv("HASS_TOKEN", "")

# ── Entity name aliases ───────────────────────────────────────────────────────
# Maps common spoken names → Home Assistant entity_id prefixes

_ENTITY_ALIASES: dict[str, str] = {
    "bedroom light":    "light.bedroom",
    "bedroom lights":   "light.bedroom",
    "living room light":"light.living_room",
    "living room lights":"light.living_room",
    "kitchen light":    "light.kitchen",
    "kitchen lights":   "light.kitchen",
    "bathroom light":   "light.bathroom",
    "office light":     "light.office",
    "all lights":       "light.all",
    "thermostat":       "climate.main",
    "ac":               "climate.main",
    "air conditioning": "climate.main",
    "heater":           "climate.main",
    "fan":              "fan.main",
    "tv":               "media_player.tv",
    "television":       "media_player.tv",
}

# ── Action mapping ────────────────────────────────────────────────────────────

_ACTION_MAP: dict[str, dict] = {
    "turn on":  {"domain": "homeassistant", "service": "turn_on"},
    "turn off": {"domain": "homeassistant", "service": "turn_off"},
    "toggle":   {"domain": "homeassistant", "service": "toggle"},
    "dim":      {"domain": "light",         "service": "turn_on", "extra": {"brightness_pct": 30}},
    "brighten": {"domain": "light",         "service": "turn_on", "extra": {"brightness_pct": 100}},
}


class SmartHome:

    async def execute(self, command: str) -> str:
        """
        Parse a natural language command and call the Home Assistant REST API.
        Returns a natural language confirmation string.
        """
        if not _HASS_TOKEN:
            return (
                "The smart home system is not configured. "
                "Please add HASS_URL and HASS_TOKEN to your .env file."
            )

        action_key, entity_id, value = self._parse_command(command)

        if not entity_id:
            return (
                f"I understood you want to control something, but I couldn't "
                f"identify the device from: '{command}'"
            )

        if not action_key:
            return f"I couldn't determine what action to take for: '{command}'"

        action = _ACTION_MAP[action_key]
        domain = action["domain"]
        service = action["service"]
        service_data: dict = {"entity_id": entity_id}

        # Merge extra params (e.g. brightness)
        if "extra" in action:
            service_data.update(action["extra"])

        # Handle temperature commands
        if value is not None and "climate" in entity_id:
            domain = "climate"
            service = "set_temperature"
            service_data["temperature"] = value

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{_HASS_URL}/api/services/{domain}/{service}",
                    headers={
                        "Authorization": f"Bearer {_HASS_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json=service_data,
                )

            if resp.status_code in (200, 201):
                entity_display = entity_id.replace("_", " ").split(".")[-1].title()
                action_display = action_key.replace("_", " ")
                return (
                    f"Done. {entity_display} has been {action_display}."
                )
            else:
                return (
                    f"Home Assistant returned status {resp.status_code}. "
                    f"The command may not have executed correctly."
                )

        except httpx.ConnectError:
            return "The smart home system appears to be offline, sir."
        except httpx.TimeoutException:
            return "The smart home system did not respond in time."
        except Exception as err:
            log.error("Smart home error: %s", err)
            return f"Smart home error: {err}"

    # ── Parsing helpers ───────────────────────────────────────────────────────

    def _parse_command(
        self, command: str
    ) -> tuple[Optional[str], Optional[str], Optional[int]]:
        """
        Returns (action_key, entity_id, optional_value).
        action_key maps to _ACTION_MAP; entity_id is a HA entity string.
        """
        lower = command.lower()

        # Detect action
        action_key: Optional[str] = None
        for key in _ACTION_MAP:
            if key in lower:
                action_key = key
                break

        # Detect entity
        entity_id: Optional[str] = None
        for alias, entity in sorted(_ENTITY_ALIASES.items(), key=lambda x: -len(x[0])):
            if alias in lower:
                entity_id = entity
                break

        # Detect numeric value (temperature)
        value: Optional[int] = None
        match = re.search(r"\b(\d+)\b", lower)
        if match:
            value = int(match.group(1))

        return action_key, entity_id, value


# ── Module-level singleton ────────────────────────────────────────────────────
smart_home = SmartHome()
