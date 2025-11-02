# Group 3: Dmitriy Maul (A00122400) , Samisha Verma (A00120599) , Abdulloh Kodirov (A00159931)
"""
This file sets up a simple online store page with an embedded chat assistant for
a sample product. It uses Flask to serve the web pages and sends users' questions
to a local language model server (Ollama) to generate answers. Only one model is
active at a time and you can select which model to use by setting the
``OLLAMA_MODEL`` environment variable before starting the app.
"""

# Import Flask classes
from flask import Flask, render_template, request, jsonify, redirect, send_from_directory
import requests , json , os , sqlite3 , datetime , threading

# Create Flask app
app = Flask(__name__)

# Images folder
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")

@app.route("/images/<path:filename>")
def images(filename: str):
    """
    Serve image files from the images directory.

    This handler looks up the requested file in the images folder and
    returns it to the browser.  The filename argument is a relative
    path inside the images directory.  Using send_from_directory
    ensures the file is served safely from the correct location.

    Args:
        filename: The requested filename relative to the images directory.

    Returns:
        A flask response with the image data.
    """
    return send_from_directory(IMAGES_DIR, filename)


# Configuration values for the endpoint
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:12b")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
# Path to the SQLite database file
DB_PATH = os.path.join(os.path.dirname(__file__), "logs.sqlite3")

# Demo product data
PRODUCTS: dict[str, dict[str, any]] = {
    "galaxy-s25-ultra": {
        "name": "Samsung Galaxy S25 Ultra",
        "rating": 4.8,
        "range": "Galaxy S25 Ultra",
        "colors": [
            {"name": "Titanium Black", "hex": "#0a0a0a"},
            {"name": "Titanium Grey", "hex": "#8f949a"},
            {"name": "Titanium Blue", "hex": "#9ec1da"},
            {"name": "Titanium Whitesilver", "hex": "#dfe8f0"},
        ],
        "capacities": ["256 GB", "512 GB", "1 TB"],
        "price_aud": 1499,
        "discount_percent": 32,
        "in_stock": True,
        "images": [
            "/images/main_sam.png",
            "/images/front_sam.png",
            "/images/common_sam.png",
            "/images/back_sam.png",
        ],
        # Key product features

        "key_features": [
            "6.9" " AMOLED, 144Hz",
            "Snapdragon Gen 4",
            "Periscope 200MP camera",
            "S Pen support",
            "5500mAh 65W fast charge",
        ],
        "returns_policy": "30 Days returns",
        "free_shipping_threshold": 250,
        # Shipping cost details (added to improve AI responses)
        # Standard shipping costs 10 AUD and express shipping costs 15 AUD.
        # The platform is based in Australia and uses AusPost for delivery.
        "shipping_cost_standard": 10,
        "shipping_cost_express": 15,
        "shipping_provider": "AusPost",
        "origin_country": "Australia",
    }
}


def init_db() -> None:
    """
    Create the SQLite database used to store chat history if it is not already present.

    The database contains a single table named ``chat_logs``. Each row records when the
    conversation happened, which product was discussed, what the user asked, what the
    assistant replied, and which model generated the reply. Calling this function
    multiple times is safe; it will not overwrite an existing table. The database
    lives at the path defined by ``DB_PATH``.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            product_slug TEXT,
            user_msg TEXT,
            ai_reply TEXT,
            model_tag TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def warmup_model() -> None:
    """
    Send a dummy request to the language model so the first real user message isn't delayed.

    When the web server starts up, the language model may not yet be loaded into memory.
    This helper makes a throwaway call to the Ollama server with a blank prompt. The
    ``keep_alive`` flag asks the model server to keep the model warm for two hours so
    subsequent requests are handled quickly. If this warm-up call fails for any reason,
    the exception is ignored and the web server still starts; the model will simply
    be loaded the first time a user asks a question.
    """
    try:
        requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": " ",
                "keep_alive": "2h",
                "options": {"num_ctx": 1024},
            },
            stream=True,
            timeout=600,
        )
    except Exception:
        # Ignore any errors; the model will load when a user asks a question.
        pass


def save_log(product_slug: str, user_msg: str, ai_reply: str) -> None:
    """
    Save one question-answer pair to the chat history database.

    This function inserts a single row into the ``chat_logs`` table, capturing the time
    of the exchange, which product the question relates to, what the user asked,
    the assistant's reply, and which model produced the answer.

    Args:
        product_slug: identifier for the product, e.g. ``"galaxy-s25-ultra"``.
        user_msg: the user's message.
        ai_reply: the assistant's response.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_logs (ts, product_slug, user_msg, ai_reply, model_tag) VALUES (?, ?, ?, ?, ?)",
        (
            datetime.datetime.utcnow().isoformat(),
            product_slug,
            user_msg,
            ai_reply,
            OLLAMA_MODEL,
        ),
    )
    conn.commit()
    conn.close()


def product_context(slug: str) -> str:
    """
    Build a brief description of a product to provide context to the language model.

    It looks up the product identified by ``slug`` and composes a sentence that includes
    the product name, its key features, price, and any available shipping information.
    This summary is prepended to the user's question before sending it to the model
    so that the AI has relevant context.

    Args:
        slug: the identifier for the product.

    Returns:
        A string summarizing the product's main features, price and shipping details.
    """
    p = PRODUCTS.get(slug, {})
    features = "; ".join(p.get("key_features", []))
    # Base context with product name, features and price
    context = f"Product: {p.get('name', '')}. Key features: {features}. Price: {p.get('price_aud', '')} AUD."
    # Include shipping costs if available
    std_cost = p.get("shipping_cost_standard")
    exp_cost = p.get("shipping_cost_express")
    if std_cost is not None and exp_cost is not None:
        context += f" Standard shipping cost is {std_cost} AUD and express shipping cost is {exp_cost} AUD."
    # Include shipping provider and origin information if available
    provider = p.get("shipping_provider")
    origin = p.get("origin_country") or "Australia"
    if provider:
        context += f" Shipping is handled by {provider} and the platform is located in {origin}."
    return context


@app.route("/")
def home():
    """
    Redirect visitors from the site root to the demo product page.

    Rather than showing a separate home page, anyone visiting ``/`` is sent directly
    to the page for the sample phone. This keeps the prototype simple.
    """
    return redirect("/product/galaxy-s25-ultra")


@app.route("/product/<slug>")
def product(slug: str):
    """
    Display the web page for a given product.

    If the requested slug isn't in the ``PRODUCTS`` dictionary we return a 404 error.
    Otherwise, we look up the product details and render them with the ``product.html``
    template. The ``default_model`` field is kept for backward compatibility but is
    currently unused by the template.

    Args:
        slug: the product identifier from the URL.

    Returns:
        A rendered page or ``("Product not found", 404)`` if the product doesn't exist.
    """
    if slug not in PRODUCTS:
        return "Product not found", 404
    return render_template(
        "product.html",
        product=PRODUCTS[slug],
        slug=slug,
        default_model=OLLAMA_MODEL,
    )


@app.route("/api/ask", methods=["POST"])
def api_ask():
    """
    Process a chat message from the front-end and return the AI's reply.

    The client sends a JSON payload with ``message`` and ``slug``. We prepend a
    short description of the product to the user's question and send it to the
    configured language model. The response is streamed back piece-by-piece and
    assembled into a single string. We also save the conversation to the history
    database. Clients cannot choose a different model via this endpoint; we always
    use the model defined in ``OLLAMA_MODEL``.
    """
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    slug = data.get("slug", "galaxy-s25-ultra")
    if not message:
        return jsonify({"reply": "Please enter a question."})
    # Quick reply for shipping cost questions. If the user asks about shipping
    # costs or delivery costs, we respond with the known shipping prices rather than
    # invoking the language model. This improves accuracy and prevents the model from
    # hallucinating generic shipping advice. The keyword list includes common English phrases for shipping costs.
    msg_lower = message.lower()
    shipping_keywords = [
        "shipping cost",
        "shipping costs",
        "delivery cost",
        "shipping price",
        "shipping fee",
        "shipping charges",
    ]
    if any(k in msg_lower for k in shipping_keywords):
        p = PRODUCTS.get(slug, {})
        std = p.get("shipping_cost_standard")
        exp = p.get("shipping_cost_express")
        provider = p.get("shipping_provider") or "AusPost"
        origin = p.get("origin_country") or "Australia"
        if std is not None and exp is not None:
            reply_text = (
                f"Standard shipping costs {std} AUD and express shipping costs {exp} AUD "
                f"within {origin}. Shipping is handled by {provider}."
            )
        else:
            reply_text = "Shipping cost information is currently unavailable."
        # Record the chat exchange
        save_log(slug, message, reply_text)
        return jsonify({"reply": reply_text})
    # Use the configured model tag
    model_tag = OLLAMA_MODEL
    # Build the prompt including extended product context (price and shipping info)
    context = product_context(slug)
    prompt = (
        "You are a helpful shopping consultant for a web store.\n"
        f"Context: {context}\n"
        f"User question: {message}\n"
        "Answer in a clear and short way."
    )
    reply_text = ""
    try:
        # Stream the response
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": model_tag,
                "prompt": prompt,
                "keep_alive": "2h",
                "options": {"temperature": 0.2, "num_ctx": 4096},
            },
            stream=True,
            timeout=120,
        )
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                obj = json.loads(line.decode("utf-8"))
                reply_text += obj.get("response", "")
            except Exception:
                # Ignore invalid JSON lines
                pass
    except requests.RequestException as e:
        reply_text = f"(AI is unavailable: {e})"
    # Record the chat exchange
    save_log(slug, message, reply_text)
    return jsonify({"reply": reply_text})


@app.route("/api/history", methods=["GET"])
def api_history():
    """
    Return recent chat history for a given product.

    The ``slug`` query parameter selects which product's history to retrieve. The
    ``limit`` parameter controls how many of the most recent exchanges to return.
    """
    slug = request.args.get("slug", "galaxy-s25-ultra")
    try:
        limit = int(request.args.get("limit", 20))
    except Exception:
        limit = 20
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT ts, user_msg, ai_reply, model_tag FROM chat_logs WHERE product_slug=? ORDER BY id DESC LIMIT ?",
        (slug, limit),
    )
    rows = cur.fetchall()
    conn.close()
    rows.reverse()
    history: list[dict[str, str]] = []
    for r in rows:
        history.append(
            {
                "ts": r[0],
                "user": r[1],
                "ai": r[2],
                "model": r[3],
            }
        )
    return jsonify({"history": history})


@app.route("/api/eta", methods=["POST"])
def api_eta():
    """
    Provide an estimated delivery date range using business days.

    For this demo we ignore the postcode entirely. A real implementation might
    consult a shipping API to estimate delivery more accurately.
    """
    data = request.get_json(silent=True) or {}
    today = datetime.date.today()

    def add_business_days(start: datetime.date, days: int) -> datetime.date:
        d = start
        added = 0
        while added < days:
            d += datetime.timedelta(days=1)
            if d.weekday() < 5:
                added += 1
        return d

    std_from = add_business_days(today, 2)
    std_to = add_business_days(today, 4)
    exp_from = add_business_days(today, 1)
    exp_to = add_business_days(today, 2)
    fmt = "%b %d"
    return jsonify(
        {
            "postcode": str(data.get("postcode", "")).strip(),
            "standard": f"{std_from.strftime(fmt)} - {std_to.strftime(fmt)}",
            "express": f"{exp_from.strftime(fmt)} - {exp_to.strftime(fmt)}",
        }
    )


if __name__ == "__main__":
    # Initialize the database and warm up the model in the background
    init_db()
    threading.Thread(target=warmup_model, daemon=True).start()
    app.run(debug=True)