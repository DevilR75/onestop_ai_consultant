# Group 3
"""
This module implements a minimal e-commerce product page with an embedded chat
assistant.  The application is built using Flask and uses a local language model
server (Ollama) to answer user questions about the product.  Only one model is
used at a time.  You can choose which model the server uses by setting the
environment variable OLLAMA_MODEL before starting the app.
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
    Create the chat history database if it does not already exist.

    This function sets up a simple SQLite database with a single
    table called chat_logs.  Each row stores the timestamp of the
    exchange, the product slug, the user message, the assistant
    response, and the model tag.  If the table already exists
    nothing will be changed.  The database file is stored at
    DB_PATH.
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
    Warm up the default language model to reduce first response latency.

    When the server starts the model may not be loaded into memory yet.  To
    avoid a slow first reply we call the local model server with a dummy
    prompt.  The keep_alive flag tells the server to keep the model in
    memory for two hours so subsequent requests are fast.  Any errors
    during this warmup are ignored so that the web server still
    starts.
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
        # If the model server user request will load
        pass


def save_log(product_slug: str, user_msg: str, ai_reply: str) -> None:
    """
    Persist a chat exchange to the SQLite database.

    Each call inserts one row into the chat_logs table.  The current
    timestamp is recorded along with the product slug, the user
    message, the assistant reply, and the configured model tag.

    Args:
        product_slug: Identifier for the product for example "galaxy-s25-ultra".
        user_msg: The user's message text.
        ai_reply: The assistant's response text.
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
    Construct a context string describing a product.

    This helper looks up a product by its slug and builds a sentence
    summarizing its name, key features, price and shipping details.  The
    returned string is used to give the language model context about
    the product when formulating a response.

    Args:
        slug: The product slug.

    Returns:
        A short description summarizing the product's key features, price and shipping information.
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
    Redirect the root URL to the default product page.

    When the user visits the site root we do not show an index page
    but immediately redirect them to the product page for our demo
    phone.  This keeps the interface simple for the prototype.
    """
    return redirect("/product/galaxy-s25-ultra")


@app.route("/product/<slug>")
def product(slug: str):
    """
    Render the product page for a given product slug.

    If the slug is not found in the PRODUCTS dictionary we return
    a 404 error.  Otherwise we pass the product data to the template
    for rendering.  The default_model value is no longer used in
    the template but remains for backward compatibility.

    Args:
        slug: The product slug from the URL path.

    Returns:
        A rendered HTML page or a tuple with an error string and status code.
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
    Receive a chat message and return a model reply.

    This endpoint expects a JSON body with the keys 'message' and
    'slug'.  It builds a prompt using the product context and the
    user question then sends it to the configured language model.
    The reply is streamed back and concatenated into a single string.
    The exchange is recorded in the history database.  We do not
    allow the client to choose a different model; the server always
    uses OLLAMA_MODEL.
    """
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    slug = data.get("slug", "galaxy-s25-ultra")
    if not message:
        return jsonify({"reply": "Please enter a question."})
    # Quick reply for shipping cost questions.  If the user asks about shipping
    # cost or delivery cost, respond with the known shipping prices without
    # invoking the language model.  This improves accuracy and ensures the
    # model does not hallucinate generic shipping advice.  Keywords cover
    # English and Russian terms for shipping cost.
    msg_lower = message.lower()
    shipping_keywords = [
        "shipping cost",
        "shipping costs",
        "delivery cost",
        "shipping price",
        "shipping fee",
        "shipping charges",
        "стоимость доставки",
        "цена доставки",
        "доставка"
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
    # Always use the configured model tag
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
    """Return recent chat history for a given product.

    The 'slug' query parameter identifies the product; 'limit'
    controls how many recent exchanges to return.
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
    """Return a simple delivery estimate based on business days.

    The postcode is ignored in this demo implementation; you may
    enhance this endpoint to consult a real shipping API.
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