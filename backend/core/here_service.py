"""
HERE routing service using HERE Routing API v8.

Provides routing and navigation information on-demand without caching.
API documentation: https://developer.here.com/documentation/routing-api/8.16.0/dev_guide/index.html
"""

import logging
import requests
from typing import Optional, Dict, Any


class HereService:
    """Service for fetching routing data from HERE API."""

    BASE_URL = "https://router.hereapi.com/v8/routes"

    def __init__(self, api_key: str):
        """
        Initialize HERE routing service.

        Args:
            api_key: HERE API key
        """
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def get_route(
        self,
        origin: str,
        destination: str,
        transport_mode: str = "car"
    ) -> Optional[Dict[str, Any]]:
        """
        Get route information between two points.

        Args:
            origin: Origin coordinates as "lat,lon" (e.g., "52.5308,13.3847")
            destination: Destination coordinates as "lat,lon" (e.g., "52.5264,13.3686")
            transport_mode: Transport mode - "car", "truck", "pedestrian", "bicycle", "scooter"

        Returns:
            Route data dict or None if request fails

        Example response:
            {
                "origin": "52.5308,13.3847",
                "destination": "52.5264,13.3686",
                "transport_mode": "car",
                "distance_meters": 1234,
                "distance_km": 1.234,
                "duration_seconds": 180,
                "duration_minutes": 3
            }
        """
        try:
            params = {
                "origin": origin,
                "destination": destination,
                "transportMode": transport_mode,
                "return": "summary",
                "apikey": self.api_key
            }

            self.logger.info(f"[HERE] Fetching route from {origin} to {destination}")
            response = requests.get(self.BASE_URL, params=params, timeout=10)

            if response.status_code == 401:
                self.logger.error("[HERE] Invalid API key")
                return None

            if response.status_code == 400:
                self.logger.error(f"[HERE] Bad request - check origin/destination format")
                return None

            response.raise_for_status()
            data = response.json()

            # Extract route summary from first route
            if not data.get("routes") or len(data["routes"]) == 0:
                self.logger.error("[HERE] No routes found")
                return None

            route = data["routes"][0]
            summary = route["sections"][0]["summary"]

            route_info = {
                "origin": origin,
                "destination": destination,
                "transport_mode": transport_mode,
                "distance_meters": summary["length"],
                "distance_km": round(summary["length"] / 1000, 2),
                "duration_seconds": summary["duration"],
                "duration_minutes": round(summary["duration"] / 60, 1)
            }

            self.logger.info(
                f"[HERE] Successfully fetched route: "
                f"{route_info['distance_km']}km, {route_info['duration_minutes']}min"
            )
            return route_info

        except requests.exceptions.Timeout:
            self.logger.error("[HERE] Request timed out")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"[HERE] Request failed: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            self.logger.error(f"[HERE] Failed to parse response: {e}")
            return None

    def format_route_response(self, route_data: Dict[str, Any]) -> str:
        """
        Format route data into a human-readable string.

        Args:
            route_data: Route data dict from get_route()

        Returns:
            Formatted route string
        """
        if not route_data:
            return "Unable to fetch route information."

        return (
            f"Route ({route_data['transport_mode']}):\n"
            f"• From: {route_data['origin']}\n"
            f"• To: {route_data['destination']}\n"
            f"• Distance: {route_data['distance_km']} km\n"
            f"• Duration: {route_data['duration_minutes']} minutes"
        )
