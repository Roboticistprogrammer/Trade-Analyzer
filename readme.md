# Alpha-Audit: LLM-Powered Trading Analytics

Alpha-Audit is a local pipeline designed to transform static trading journals (PDF) into actionable behavioral insights. By leveraging **OpenRouter** for inference and **Python** for data extraction, this tool identifies "strategy drift" and psychological patterns in trading performance.

## 🚀 Features
- **PDF Extraction:** Automated parsing of trade logs into structured JSON.
- **Cognitive Analysis:** Uses OpenRouter (Llama 3/3.3) to audit trade execution against planned setups.

## 🛠️ Prerequisites
- **OS:** Ubuntu 22.04 
- **Python:** 3.10+
- **OpenRouter API Key:** Ensure your key is configured for `:free` models (refer to the setup guide).

## ⚙️ Setup and Run

1. Clone the repository and enter the project directory:

   ```bash
   git clone https://github.com/Roboticistprogrammer/Trade-Analyzer.git
   cd Trade-Analyzer
   ```

2. Create and activate a Python virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install the project dependencies:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root and add your OpenRouter settings:

   ```env
   OPENROUTER_API_KEY=your_openrouter_api_key
   OPENROUTER_MODEL=openai/gpt-4o-mini
   ```

   The model is optional and can also be changed from the web interface. You may
   leave the API key out of `.env` and enter it in the interface for each run.

5. Start the platform:

   ```bash
   python -m uvicorn app.main:app --reload
   ```

6. Open [http://localhost:8000](http://localhost:8000) in your browser. Upload a
   Binance-style trading journal PDF, confirm the model and API key, and select
   **Analyze PDF**. The platform will extract the trades, organize them into
   trade cycles, run the OpenRouter analysis, and display downloadable results.

Press `Ctrl+C` in the terminal to stop the platform. Run
`source .venv/bin/activate` again whenever you return to the project in a new
terminal session.
