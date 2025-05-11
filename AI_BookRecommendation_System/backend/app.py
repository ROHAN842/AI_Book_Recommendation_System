from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import AzureOpenAI
from dotenv import load_dotenv
import os
import traceback  # For detailed error logs
import re  # For sanitization
from werkzeug.middleware.proxy_fix import ProxyFix  # SECURITY: optional for reverse proxy
from flask_talisman import Talisman  # SECURITY: for HTTP security headers

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# SECURITY: Set max content length (1MB max request)
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB

# SECURITY: Add HTTP security headers with relaxed CSP for Angular + images
csp = {
    'default-src': [
        '\'self\'',
        'http://localhost:4200'
    ],
    'img-src': '*',
}

Talisman(app, content_security_policy=csp, force_https=False)


# SECURITY: Fix proxy headers if using behind proxy (optional, depends on deployment)
app.wsgi_app = ProxyFix(app.wsgi_app)

# Allow CORS only for frontend origin
CORS(app, resources={r"/recommend": {"origins": "http://localhost:4200"}})

# Load API credentials
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

# Initialize Azure OpenAI Client
client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    api_version=OPENAI_API_VERSION
)

# Function to sanitize prompts
def sanitize_prompt(text):
    """Removes words that might trigger OpenAI's content policy filters"""
    forbidden_words = ["violence", "death", "weapon", "kill", "war", "politics", "explicit", "adult", "nsfw"]
    
    # SECURITY: also strip HTML tags
    text = re.sub(r'<.*?>', '', text)

    # Replace forbidden words with asterisks
    for word in forbidden_words:
        text = re.sub(rf"\b{word}\b", "***", text, flags=re.IGNORECASE)
    
    return text

@app.route('/recommend', methods=['POST'])
def get_book_recommendations():
    """Fetches book recommendations with images."""
    try:
        # SECURITY: validate JSON content-type
        if not request.is_json:
            return jsonify({"error": "Invalid content type, JSON expected"}), 400

        data = request.get_json()  # Get JSON data from Angular
        user_input = data.get("query", "").strip()

        # SECURITY: input length check
        if len(user_input) > 200:
            return jsonify({"error": "Input too long"}), 400

        # Updated prompt logic
        prompt = f"""
        If "{user_input}" is a genre, recommend books in that genre. 
        If "{user_input}" is an author's name, list only books written by that author.
        Provide a short description (1-2 lines) for each book.
        Format the output as: 
        'Book Title' by Author Name - Short description.
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a book recommendation assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000  
        )

        recommendations = response.choices[0].message.content.strip()
        book_list = []

        for line in recommendations.split('\n'):
            line = line.strip()
            if not line:
                continue

            match = line.split(' by ')
            if len(match) < 2:
                continue

            title = sanitize_prompt(match[0].strip())  # Sanitize title
            author_desc = sanitize_prompt(match[1].strip())  # Sanitize author

            # Generate book cover image
            image_response = client.images.generate(
                model="dall-e-3",
                prompt=f"A beautiful and artistic book cover for '{title}' by {author_desc}.",
                n=1,
                size="1024x1024"
            )

            image_url = image_response.data[0].url if image_response.data else ""
            
            book_list.append({
                "title": title,
                "author": author_desc,
                "image_url": image_url
            })

        return jsonify({"recommendations": book_list})  # Send JSON response to Angular

    except Exception as e:
        traceback.print_exc()  # Print full error traceback in console
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # SECURITY: Never use debug=True in production
    app.run(host="0.0.0.0", port=5001)
