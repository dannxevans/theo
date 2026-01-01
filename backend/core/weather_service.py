"""
Weather service using OpenWeather API.

Provides weather information on-demand without caching.
API documentation: https://openweathermap.org/current
"""

import logging
import requests
from typing import Optional, Dict, Any


class WeatherService:
    """Service for fetching weather data from OpenWeather API."""

    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, api_key: str):
        """
        Initialize weather service.

        Args:
            api_key: OpenWeather API key
        """
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def get_weather(
        self,
        location: str,
        units: str = "metric"
    ) -> Optional[Dict[str, Any]]:
        """
        Get current weather for a location.

        Args:
            location: City name or "city,country_code" (e.g., "London,UK")
            units: Temperature units - "metric" (Celsius), "imperial" (Fahrenheit), or "standard" (Kelvin)

        Returns:
            Weather data dict or None if request fails

        Example response:
            {
                "location": "London, GB",
                "temperature": 15.2,
                "feels_like": 14.1,
                "humidity": 72,
                "description": "overcast clouds",
                "wind_speed": 3.5,
                "units": "metric"
            }
        """
        try:
            params = {
                "q": location,
                "appid": self.api_key,
                "units": units
            }

            self.logger.info(f"[WEATHER] Fetching weather for: {location}")
            response = requests.get(self.BASE_URL, params=params, timeout=10)

            if response.status_code == 401:
                self.logger.error("[WEATHER] Invalid API key")
                return None

            if response.status_code == 404:
                self.logger.error(f"[WEATHER] Location not found: {location}")
                return None

            response.raise_for_status()
            data = response.json()

            # Extract relevant weather information
            weather_info = {
                "location": f"{data['name']}, {data['sys']['country']}",
                "temperature": data['main']['temp'],
                "feels_like": data['main']['feels_like'],
                "humidity": data['main']['humidity'],
                "description": data['weather'][0]['description'],
                "wind_speed": data['wind']['speed'],
                "units": units
            }

            self.logger.info(f"[WEATHER] Successfully fetched weather for {weather_info['location']}")
            return weather_info

        except requests.exceptions.Timeout:
            self.logger.error("[WEATHER] Request timed out")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"[WEATHER] Request failed: {e}")
            return None
        except (KeyError, ValueError) as e:
            self.logger.error(f"[WEATHER] Failed to parse response: {e}")
            return None

    def format_weather_response(self, weather_data: Dict[str, Any]) -> str:
        """
        Format weather data into a human-readable string.

        Args:
            weather_data: Weather data dict from get_weather()

        Returns:
            Formatted weather string
        """
        if not weather_data:
            return "Unable to fetch weather information."

        units_symbol = "°C" if weather_data["units"] == "metric" else "°F"
        if weather_data["units"] == "standard":
            units_symbol = "K"

        wind_units = "m/s" if weather_data["units"] == "metric" else "mph"

        return (
            f"Weather in {weather_data['location']}:\n"
            f"• Temperature: {weather_data['temperature']}{units_symbol} "
            f"(feels like {weather_data['feels_like']}{units_symbol})\n"
            f"• Conditions: {weather_data['description'].capitalize()}\n"
            f"• Humidity: {weather_data['humidity']}%\n"
            f"• Wind Speed: {weather_data['wind_speed']} {wind_units}"
        )
