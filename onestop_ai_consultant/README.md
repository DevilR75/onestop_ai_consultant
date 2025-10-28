# OneStop AI Consultant — Flask + Ollama

This project is a simple web prototype of a product page with a virtual AI consultant chat.
It uses a local model server through **Ollama**.  Only one model runs at a time.  You can
choose which model the server uses by setting the `OLLAMA_MODEL` environment variable
before starting the application.  The client does not provide a model selector.

## Features

- Product page with a gallery and active thumbnail selection
- Floating chat button and interactive chat widget with a large viewport
- Chat history stored in a local SQLite database
- Simple delivery estimate endpoint for demonstration
- Warm‑up of the default model to reduce the delay before the first reply

## Requirements

- Python 3.10 or later
- [Ollama](https://ollama.ai) installed locally
- At least one model pulled via `ollama` (see below)

## Quick Start (common steps)

1. **Navigate to the project folder**: after unpacking, change directory into `onestop_ai_consultant`.
2. **Create and activate a virtual environment**: this isolates dependencies.
3. **Install the Python packages**: `pip install -r requirements.txt`.
4. **Install and start Ollama**: follow the official installation instructions for your platform and pull the models you need:
   - `ollama pull gemma3:12b`
   - `ollama pull gemma3:4b` (optional for a lighter model)
5. **Run the server**: `python app.py`.
6. **Browse the app**: open `http://127.0.0.1:5000` in your web browser.

## Running on Windows (PowerShell)

```powershell
cd .\onestop_ai_consultant
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\activate
pip install -r requirements.txt
ollama pull gemma3:12b # optional larger model
ollama pull gemma3:4b  
python app.py
# Now open http://127.0.0.1:5000 in your browser
```

To use `gemma3:4b` or any other model by default, set an environment variable before starting the server:

```powershell
$env:OLLAMA_MODEL="gemma3:4b"
python app.py
```

## Running on Linux (bash)

```bash
cd onestop_ai_consultant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
ollama pull gemma3:12b
ollama pull gemma3:4b  # optional
python app.py
# Visit http://127.0.0.1:5000 in your browser
```

To switch the default model in Linux or macOS, export the `OLLAMA_MODEL` variable:

```bash
export OLLAMA_MODEL="gemma3:4b"
python app.py
```

## Running on macOS (zsh)

```zsh
cd onestop_ai_consultant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
ollama pull gemma3:12b
ollama pull gemma3:4b  # optional
python app.py
# Navigate to http://127.0.0.1:5000
```

You can choose a different default model by setting `OLLAMA_MODEL` as shown above.

## Model selection

There is **no model selector in the user interface**.  The Flask backend
always uses the model specified by the `OLLAMA_MODEL` environment variable.
To switch models, set `OLLAMA_MODEL` before running `python app.py`.

## Verify that Ollama is running

If you encounter problems connecting to the model server, test it from the
command line:

```bash
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma3:4b","prompt":"hello"}'
```

If this returns text from the model, the server is operational.

## Project structure

```
onestop_ai_consultant/
  app.py           # Flask server and API endpoints
  requirements.txt # Python dependencies
  README.md        # Project overview and usage instructions
  images/          # Product images (place your PNGs here)
  static/
    app.js        # Front‑end logic for chat and UI interactions
    style.css     # Styling for the page and chat
  templates/
    layout.html   # Base HTML template
    product.html  # Product page with chat and 3D modal
```

## Troubleshooting

- **Execution policy on Windows**: If PowerShell blocks script activation, run
  `Set‑ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` before
  activating your virtual environment.
- **Model server not reachable**: Ensure Ollama is running by issuing a
  simple request with `curl` as shown above.  You must pull at least one
  model before starting the Flask server.
- **Memory constraints**: The `gemma3:12b` model requires more memory (RAM and
  potentially GPU).  Use the `gemma3:4b` model if you encounter out‑of‑memory
  errors.
- **Warm up time**: The first response may be slower while the model loads.
  Subsequent responses should be faster due to the keep‑alive setting.