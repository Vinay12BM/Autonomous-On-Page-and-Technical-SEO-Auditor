import os
import requests
import sqlite3
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# --- Configuration ---
DATABASE = 'users.db'
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"
app = Flask(__name__)
CORS(app)

# --- SQLite Database Setup ---

def get_db():
    """Establishes a database connection or returns the current one."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # Allows accessing columns by name
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initializes the database schema (creates the users table)."""
    with app.app_context():
        db = get_db()
        # Create users table if it doesn't exist
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        db.commit()

# Initialize the database on startup
with app.app_context():
    init_db()

# --- Authentication Endpoints ---

@app.route('/auth/register', methods=['POST'])
def register():
    data = request.json
    first_name = data.get('firstName')
    last_name = data.get('lastName')
    email = data.get('email')
    password = data.get('password')

    if not all([first_name, last_name, email, password]):
        return jsonify({"error": "Missing required fields."}), 400

    db = get_db()
    # Hash the password securely
    password_hash = generate_password_hash(password)

    try:
        cursor = db.execute(
            "INSERT INTO users (first_name, last_name, email, password_hash) VALUES (?, ?, ?, ?)",
            (first_name, last_name, email, password_hash)
        )
        db.commit()
        return jsonify({
            "success": True, 
            "message": "Registration successful.",
            "userId": cursor.lastrowid
        }), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already registered."}), 409
    except Exception as e:
        app.logger.error(f"Database error during registration: {e}")
        return jsonify({"error": "Internal server error during registration."}), 500

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"error": "Missing email or password."}), 400

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if user and check_password_hash(user['password_hash'], password):
        # Successful login
        return jsonify({
            "success": True,
            "userId": user['user_id'],
            "firstName": user['first_name'],
            "lastName": user['last_name'],
            "email": user['email']
        }), 200
    else:
        return jsonify({"error": "Invalid email or password."}), 401

# --- AI Integration Endpoints ---

@app.route('/generate-fix', methods=['POST'])
def generate_fix():
    # ... (AI logic remains the same) ...
    if not GEMINI_API_KEY:
        return jsonify({"error": "Gemini API key is not configured on the server."}), 500

    data = request.json
    issue_id = data.get('issueId')
    context = data.get('context', {})

    if not issue_id:
        return jsonify({"error": "issueId is required."}), 400

    # --- PROMPT CONSTRUCTION LOGIC (Enhanced for context) ---
    prompt = ""
    
    if issue_id == 'no-h1':
        current_topic = context.get('topic', 'a generic web page')
        prompt = f"Act as an expert SEO copywriter. Generate a concise, highly engaging H1 tag (single sentence, no quotes) for a webpage about the topic: '{current_topic}'. The H1 must target strong search intent."
    
    elif issue_id == 'title-length':
        original_title = context.get('title', 'A very long, unoptimized title.')
        prompt = f"Act as an expert SEO consultant. Shorten the following webpage title to under 60 characters for maximum SEO effectiveness and better search results display, keeping the core meaning: \"{original_title}\""
    
    elif issue_id == 'image-alt-text':
        image_src = context.get('src', 'a corporate logo')
        prompt = f"Act as an accessibility specialist. Write a brief, descriptive alt text (under 12 words, no quotes) for an image that is described as '{image_src}'. Focus on describing the image content for screen readers and SEO."
    
    elif issue_id == 'meta-description':
        current_topic = context.get('topic', 'company services and features')
        prompt = f"Act as an expert marketer. Write a compelling meta description (under 160 characters, no quotes) for a webpage about '{current_topic}' to maximize click-through rates from search results. Make it action-oriented and relevant."

    else:
        return jsonify({"error": "Unsupported issueId for AI content generation."}), 400

    # --- API Communication ---
    payload = { "contents": [{ "parts": [{ "text": prompt }] }] }
    headers = { 'Content-Type': 'application/json' }
    params = { 'key': GEMINI_API_KEY }

    try:
        response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=payload)
        response.raise_for_status()
        
        result = response.json()
        suggestion = result['candidates'][0]['content']['parts'][0]['text'].strip().replace('"', '')

        return jsonify({"suggestion": suggestion})

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error calling Gemini API: {e}")
        error_details = "An unknown error occurred."
        if e.response is not None:
            try:
                error_details = e.response.json()
            except ValueError:
                error_details = e.response.text
        return jsonify({"error": "Failed to communicate with the Gemini API. Check API key or quota.", "details": str(e)}), 502
    except (KeyError, IndexError) as e:
        app.logger.error(f"Error parsing Gemini API response: {e}")
        return jsonify({"error": "Invalid response format from the Gemini API."}), 500

@app.route('/apply-fix', methods=['POST'])
def apply_fix():
    # --- SIMULATION LOGIC ---
    data = request.json
    issue_id = data.get('issueId')
    suggestion = data.get('suggestion')

    if not issue_id or not suggestion:
        return jsonify({"error": "issueId and suggestion are required."}), 400

    print(f"\n--- FIX APPLIED (SIMULATED) ---")
    print(f"Issue ID: {issue_id}")
    print(f"Applied Fix: {suggestion}")
    print(f"-------------------------------")

    return jsonify({"message": f"Fix for '{issue_id}' has been successfully applied (simulated)."}), 200

if __name__ == '__main__':
    app.run(port=5001, debug=True)
