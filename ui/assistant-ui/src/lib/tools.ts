import { z } from "zod";

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

// 1. Weather Tool Schema (Open-Meteo REST API)
export const weatherToolSchema = z.object({
  city: z.string().describe("The city name, e.g., 'Tokyo', 'London', 'New York', 'Paris'"),
});

export type WeatherToolArgs = z.infer<typeof weatherToolSchema>;

// 2. Crypto Price Tool Schema (CoinGecko REST API)
export const cryptoToolSchema = z.object({
  coin: z.string().describe("The cryptocurrency name or symbol, e.g., 'bitcoin', 'ethereum', 'solana', 'cardano', 'dogecoin'"),
});

export type CryptoToolArgs = z.infer<typeof cryptoToolSchema>;

// 3. Wikipedia Summary Tool Schema (Wikipedia REST API)
export const wikiToolSchema = z.object({
  topic: z.string().describe("The article topic to lookup on Wikipedia, e.g., 'Artificial intelligence', 'Quantum computing', 'Next.js'"),
});

export type WikiToolArgs = z.infer<typeof wikiToolSchema>;

// Open AI Function Specifications
export const TOOLS_SPECIFICATIONS = [
  {
    type: "function",
    function: {
      name: "get_weather",
      description: "Fetches live weather conditions (temperature, humidity, wind speed, weather code) for a city using an external HTTP API (Open-Meteo).",
      parameters: {
        type: "object",
        properties: {
          city: {
            type: "string",
            description: "The city name, e.g., 'Tokyo', 'London', 'New York', 'Paris'",
          },
        },
        required: ["city"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "fetch_crypto_price",
      description: "Fetches real-time cryptocurrency market data (price in USD, 24h change %, market status) from an external HTTP API (CoinGecko).",
      parameters: {
        type: "object",
        properties: {
          coin: {
            type: "string",
            description: "The cryptocurrency ID or symbol, e.g., 'bitcoin', 'ethereum', 'solana', 'dogecoin', 'cardano'",
          },
        },
        required: ["coin"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "fetch_wiki_summary",
      description: "Fetches structured summary, article text, and thumbnail image for any topic using the Wikipedia REST API.",
      parameters: {
        type: "object",
        properties: {
          topic: {
            type: "string",
            description: "The topic or subject to query on Wikipedia, e.g. 'Artificial intelligence', 'Quantum computing'",
          },
        },
        required: ["topic"],
      },
    },
  },
];
