# Assistant-UI LocalRuntime Example with External HTTP Tools & OpenAI API

A modern React & Next.js application demonstrating the **`assistant-ui` framework** using **`LocalRuntime`** (`useLocalRuntime`), OpenAI API (`gpt-4o-mini`), and **External HTTP REST Tools** with custom Generative UI tool rendering.

## Features

- ⚡ **`assistant-ui` Framework**: Connects frontend UI to a custom backend model via `useLocalRuntime` and `ChatModelAdapter`.
- 🔑 **OpenAI API Key Integration**: Reads `OPENAI_API_KEY` from `.env.local` or environment variables, with a fallback interactive UI configuration modal.
- 🌐 **External HTTP REST API Tools**:
  - `get_weather`: Fetches live weather data from **Open-Meteo REST API** (`https://api.open-meteo.com/v1/forecast`).
  - `fetch_crypto_price`: Fetches real-time crypto prices from **CoinGecko REST API** (`https://api.coingecko.com/api/v3/simple/price`).
  - `fetch_wiki_summary`: Fetches topic summaries & images from **Wikipedia REST API** (`https://en.wikipedia.org/api/rest_v1/page/summary/...`).
- 🎨 **Generative Tool UI Rendering**: Custom tool cards (`WeatherToolUI`, `CryptoToolUI`, `WikiToolUI`) rendered dynamically via `makeAssistantToolUI`.
- 🔮 **Prompt Suggestions**: Interactive quick prompt pills for one-click HTTP tool invocation.

## Getting Started

### 1. Set Up Environment Variables
Create a `.env.local` file in the project root:

```env
OPENAI_API_KEY=sk-proj-...
```

*(Alternatively, you can click "API Key Settings" in the header to enter your API key interactively in the browser.)*

### 2. Run the Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to test the app.

### 3. Build for Production

```bash
npm run build
npm run start
```

## Project Structure

```
src/
├── app/
│   ├── api/chat/route.ts        # Next.js API route handling OpenAI & tool calls
│   ├── globals.css              # Dark theme & custom scrollbar styles
│   └── page.tsx                 # Main layout
├── components/
│   ├── Header.tsx               # Header with API key settings & status badges
│   ├── AssistantChat.tsx        # Assistant-UI chat runtime container
│   └── tools/
│       ├── WeatherToolUI.tsx    # Generative UI card for Weather HTTP tool
│       ├── CryptoToolUI.tsx     # Generative UI card for Crypto HTTP tool
│       └── WikiToolUI.tsx       # Generative UI card for Wikipedia HTTP tool
└── lib/
    ├── chat-adapter.ts          # ChatModelAdapter for useLocalRuntime
    ├── http-tool-executor.ts    # External HTTP REST API fetch handlers
    └── tools.ts                 # OpenAI function definitions & schemas
```
