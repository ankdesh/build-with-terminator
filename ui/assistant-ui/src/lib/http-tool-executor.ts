/**
 * External HTTP Tool Executor
 * Handles actual HTTP REST requests to external web APIs.
 */

export interface WeatherToolResult {
  success: boolean;
  city: string;
  country?: string;
  temperature?: number;
  humidity?: number;
  windSpeed?: number;
  weatherCondition?: string;
  error?: string;
}

export interface CryptoToolResult {
  success: boolean;
  coin: string;
  symbol?: string;
  priceUsd?: number;
  change24h?: number;
  lastUpdated?: string;
  error?: string;
}

export interface WikiToolResult {
  success: boolean;
  topic: string;
  title?: string;
  extract?: string;
  thumbnailUrl?: string;
  contentUrl?: string;
  error?: string;
}

function decodeWeatherCode(code: number): string {
  if (code === 0) return "Clear sky";
  if (code >= 1 && code <= 3) return "Mainly clear, partly cloudy";
  if (code >= 45 && code <= 48) return "Foggy";
  if (code >= 51 && code <= 55) return "Drizzle";
  if (code >= 61 && code <= 65) return "Rain";
  if (code >= 71 && code <= 75) return "Snow fall";
  if (code >= 80 && code <= 82) return "Rain showers";
  if (code >= 95) return "Thunderstorm";
  return "Cloudy";
}

export async function executeWeatherHttpTool(city: string): Promise<WeatherToolResult> {
  try {
    // 1. HTTP Geocoding API Call
    const geoUrl = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1&language=en&format=json`;
    const geoRes = await fetch(geoUrl);
    if (!geoRes.ok) {
      throw new Error(`Geocoding HTTP error status ${geoRes.status}`);
    }
    const geoData = await geoRes.json();
    if (!geoData.results || geoData.results.length === 0) {
      return { success: false, city, error: `City '${city}' not found.` };
    }

    const { latitude, longitude, name, country } = geoData.results[0];

    // 2. HTTP Weather Forecast API Call
    const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m`;
    const weatherRes = await fetch(weatherUrl);
    if (!weatherRes.ok) {
      throw new Error(`Weather HTTP error status ${weatherRes.status}`);
    }

    const weatherData = await weatherRes.json();
    const current = weatherData.current;

    return {
      success: true,
      city: name || city,
      country: country || "",
      temperature: current?.temperature_2m,
      humidity: current?.relative_humidity_2m,
      windSpeed: current?.wind_speed_10m,
      weatherCondition: decodeWeatherCode(current?.weather_code ?? 0),
    };
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    return { success: false, city, error: errorMsg };
  }
}

export async function executeCryptoHttpTool(coin: string): Promise<CryptoToolResult> {
  try {
    const coinId = coin.toLowerCase().trim();
    // HTTP CoinGecko API Call
    const url = `https://api.coingecko.com/api/v3/simple/price?ids=${encodeURIComponent(coinId)}&vs_currencies=usd&include_24hr_change=true`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`CoinGecko HTTP error status ${res.status}`);
    }
    const data = await res.json();
    
    if (!data[coinId]) {
      // Fallback map for common tickers
      const symbolMap: Record<string, string> = {
        btc: "bitcoin",
        eth: "ethereum",
        sol: "solana",
        doge: "dogecoin",
        ada: "cardano",
        xrp: "ripple",
      };
      if (symbolMap[coinId]) {
        return executeCryptoHttpTool(symbolMap[coinId]);
      }
      return { success: false, coin, error: `Cryptocurrency '${coin}' not found on CoinGecko HTTP API.` };
    }

    const info = data[coinId];
    return {
      success: true,
      coin: coinId,
      symbol: coinId.toUpperCase(),
      priceUsd: info.usd,
      change24h: info.usd_24h_change,
      lastUpdated: new Date().toLocaleTimeString(),
    };
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    return { success: false, coin, error: errorMsg };
  }
}

export async function executeWikiHttpTool(topic: string): Promise<WikiToolResult> {
  try {
    const url = `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(topic)}`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Wikipedia REST HTTP API error status ${res.status}`);
    }
    const data = await res.json();

    if (data.type === "https://mediawiki.org/wiki/HyperSwitch/errors/not_found") {
      return { success: false, topic, error: `Topic '${topic}' not found on Wikipedia.` };
    }

    return {
      success: true,
      topic,
      title: data.title,
      extract: data.extract,
      thumbnailUrl: data.thumbnail?.source,
      contentUrl: data.content_urls?.desktop?.page,
    };
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    return { success: false, topic, error: errorMsg };
  }
}

export async function executeHttpToolByName(name: string, args: Record<string, unknown>) {
  if (name === "get_weather") {
    return await executeWeatherHttpTool(String(args.city || "Tokyo"));
  }
  if (name === "fetch_crypto_price") {
    return await executeCryptoHttpTool(String(args.coin || "bitcoin"));
  }
  if (name === "fetch_wiki_summary") {
    return await executeWikiHttpTool(String(args.topic || "Artificial Intelligence"));
  }
  throw new Error(`Unknown tool name '${name}'`);
}
