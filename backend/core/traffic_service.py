"""
Traffic service using HERE Routing API v8.

Provides traffic estimates and geocoding on-demand without caching.
Builds on the HereService from Phase 2 for routing functionality.
API documentation: https://developer.here.com/documentation/routing-api/8.16.0/dev_guide/index.html
"""

import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime


class TrafficService:
    """Service for fetching traffic estimates and geocoding from HERE API."""

    BASE_URL = "https://router.hereapi.com/v8/routes"
    GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"

    def __init__(self, api_key: str):
        """
        Initialize traffic service.

        Args:
            api_key: HERE API key
        """
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def get_traffic_estimate(
        self,
        origin: str,
        destination: str,
        departure_time: Optional[datetime] = None,
        transport_mode: str = "car"
    ) -> Optional[Dict[str, Any]]:
        """
        Get traffic estimate between two points with optional departure time.

        Args:
            origin: Origin coordinates as "lat,lon" or address string
            destination: Destination coordinates as "lat,lon" or address string
            departure_time: Optional departure time for traffic prediction
            transport_mode: Transport mode - "car", "truck", "pedestrian", "bicycle"

        Returns:
            Traffic data dict or None if request fails

        Example response:
            {
                "origin": "52.5308,13.3847",
                "destination": "52.5264,13.3686",
                "transport_mode": "car",
                "distance_meters": 1234,
                "distance_km": 1.234,
                "duration_seconds": 180,
                "duration_minutes": 3,
                "duration_in_traffic_seconds": 240,
                "duration_in_traffic_minutes": 4,
                "traffic_delay_seconds": 60,
                "departure_time": "2024-01-15T14:00:00"
            }
        """
        try:
            # Geocode if necessary
            origin_coords = self._ensure_coordinates(origin)
            destination_coords = self._ensure_coordinates(destination)

            if not origin_coords or not destination_coords:
                self.logger.error("[TRAFFIC] Failed to geocode origin or destination")
                return None

            params = {
                "origin": origin_coords,
                "destination": destination_coords,
                "transportMode": transport_mode,
                "return": "summary",
                "apikey": self.api_key
            }

            # Add departure time for traffic prediction
            if departure_time:
                params["departureTime"] = departure_time.strftime("%Y-%m-%dT%H:%M:%S")

            self.logger.info(
                f"[TRAFFIC] Fetching traffic estimate from {origin_coords} to {destination_coords}"
            )

            response = requests.get(self.BASE_URL, params=params, timeout=5)

            if response.status_code == 401:
                self.logger.error("[TRAFFIC] Invalid API key")
                return None

            if response.status_code == 400:
                self.logger.error("[TRAFFIC] Bad request - check origin/destination format")
                return None

            response.raise_for_status()
            data = response.json()

            # Extract route summary
            if not data.get("routes") or len(data["routes"]) == 0:
                self.logger.error("[TRAFFIC] No routes found")
                return None

            route = data["routes"][0]
            summary = route["sections"][0]["summary"]

            traffic_info = {
                "origin": origin_coords,
                "destination": destination_coords,
                "transport_mode": transport_mode,
                "distance_meters": summary["length"],
                "distance_km": round(summary["length"] / 1000, 2),
                "duration_seconds": summary["duration"],
                "duration_minutes": round(summary["duration"] / 60, 1),
            }

            # Add traffic-specific data if available
            if "baseDuration" in summary:
                base_duration = summary["baseDuration"]
                actual_duration = summary["duration"]
                traffic_delay = actual_duration - base_duration

                traffic_info.update({
                    "duration_in_traffic_seconds": actual_duration,
                    "duration_in_traffic_minutes": round(actual_duration / 60, 1),
                    "traffic_delay_seconds": traffic_delay,
                    "traffic_delay_minutes": round(traffic_delay / 60, 1),
                })

            if departure_time:
                traffic_info["departure_time"] = departure_time.isoformat()

            self.logger.info(
                f"[TRAFFIC] Successfully fetched traffic: "
                f"{traffic_info.get('duration_in_traffic_minutes', traffic_info['duration_minutes'])}min"
            )
            return traffic_info

        except requests.exceptions.Timeout:
            self.logger.error("[TRAFFIC] Request timed out")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"[TRAFFIC] Request failed: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            self.logger.error(f"[TRAFFIC] Failed to parse response: {e}")
            return None

    def _ensure_coordinates(self, location: str) -> Optional[str]:
        """
        Ensure location is in coordinate format, geocode if necessary.

        Args:
            location: Either "lat,lon" coordinates or address string

        Returns:
            Coordinates as "lat,lon" or None if geocoding fails
        """
        # Check if already coordinates (format: "52.5308,13.3847")
        parts = location.split(",")
        if len(parts) == 2:
            try:
                float(parts[0].strip())
                float(parts[1].strip())
                return location.strip()
            except ValueError:
                pass

        # Need to geocode
        return self._geocode_location(location)

    def _geocode_location(self, address: str) -> Optional[str]:
        """
        Convert address to lat/lng coordinates using HERE Geocoding API.

        Args:
            address: Address string (e.g., "Westfield London")

        Returns:
            Coordinates as "lat,lon" or None if geocoding fails
        """
        try:
            params = {
                "q": address,
                "apikey": self.api_key,
                "limit": 1
            }

            self.logger.info(f"[TRAFFIC] Geocoding address: {address}")
            response = requests.get(self.GEOCODE_URL, params=params, timeout=5)

            if response.status_code != 200:
                self.logger.error(f"[TRAFFIC] Geocoding failed with status {response.status_code}")
                return None

            data = response.json()

            if not data.get("items") or len(data["items"]) == 0:
                self.logger.error(f"[TRAFFIC] No geocoding results for: {address}")
                return None

            position = data["items"][0]["position"]
            coords = f"{position['lat']},{position['lng']}"

            self.logger.info(f"[TRAFFIC] Geocoded '{address}' to {coords}")
            return coords

        except requests.exceptions.Timeout:
            self.logger.error("[TRAFFIC] Geocoding request timed out")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"[TRAFFIC] Geocoding request failed: {e}")
            return None
        except (KeyError, ValueError) as e:
            self.logger.error(f"[TRAFFIC] Failed to parse geocoding response: {e}")
            return None

    def format_traffic_response(self, traffic_data: Dict[str, Any]) -> str:
        """
        Format traffic data into a human-readable string.

        Args:
            traffic_data: Traffic data dict from get_traffic_estimate()

        Returns:
            Formatted traffic string
        """
        if not traffic_data:
            return "Unable to fetch traffic information."

        response = (
            f"Traffic Estimate ({traffic_data['transport_mode']}):\n"
            f"• From: {traffic_data['origin']}\n"
            f"• To: {traffic_data['destination']}\n"
            f"• Distance: {traffic_data['distance_km']} km\n"
        )

        if "duration_in_traffic_minutes" in traffic_data:
            response += f"• Duration (with traffic): {traffic_data['duration_in_traffic_minutes']} minutes\n"
            if traffic_data.get("traffic_delay_minutes", 0) > 0:
                response += f"• Traffic Delay: +{traffic_data['traffic_delay_minutes']} minutes\n"
        else:
            response += f"• Duration: {traffic_data['duration_minutes']} minutes\n"

        if "departure_time" in traffic_data:
            response += f"• Departure: {traffic_data['departure_time']}"

        return response
