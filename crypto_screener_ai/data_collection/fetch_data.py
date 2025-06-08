import requests
import json
import datetime

def get_coingecko_data(coin_id: str, vs_currency: str, days: int):
    """
    Fetches historical market data for a specific coin from CoinGecko.

    Args:
        coin_id: The ID of the coin (e.g., "bitcoin").
        vs_currency: The currency to get the price in (e.g., "usd").
        days: The number of days of historical data to fetch.

    Returns:
        A list of lists, where each inner list is [timestamp_iso, price],
        or None if an error occurs.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency={vs_currency}&days={days}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        prices = data.get('prices', [])
        normalized_prices = []
        for timestamp_ms, price in prices:
            # Convert timestamp from milliseconds to seconds
            timestamp_s = timestamp_ms / 1000
            # Create datetime object
            dt_object = datetime.datetime.fromtimestamp(timestamp_s)
            # Format to ISO 8601
            iso_format = dt_object.isoformat()
            normalized_prices.append([iso_format, price])
        return normalized_prices
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from CoinGecko: {e}")
        return None
    except json.JSONDecodeError:
        print("Error decoding JSON response from CoinGecko.")
        return None

def save_data_to_json(data: list, filename: str):
    """
    Saves data to a JSON file.

    Args:
        data: The data to save.
        filename: The name of the file to save the data to.
                  The file will be saved in the current script's directory.
    """
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Data successfully saved to {filename}")
    except IOError as e:
        print(f"Error saving data to JSON file: {e}")

if __name__ == "__main__":
    coin_id = "bitcoin"
    vs_currency = "usd"
    days = 7  # Fetch data for the last 7 days

    print(f"Fetching data for {coin_id} in {vs_currency} for the last {days} days...")
    price_data = get_coingecko_data(coin_id, vs_currency, days)

    if price_data:
        # Construct filename relative to the script's location
        # The problem asks for the file to be in crypto_screener_ai/data_collection/
        # which is where this script is located.
        output_filename = f"{coin_id}_{vs_currency}_{days}_days_data.json"
        print(f"Saving data to {output_filename}...")
        save_data_to_json(price_data, output_filename)
    else:
        print(f"Failed to fetch data for {coin_id}.")
