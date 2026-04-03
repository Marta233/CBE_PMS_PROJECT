#!/bin/bash

echo "🚀 Setting up project structure and pushing to GitHub..."

# =========================
# CREATE STRUCTURE
# =========================

mkdir -p app/services app/models app/database app/utils
mkdir -p notebooks tests scripts

# Core files
touch run.py requirements.txt .env .gitignore README.md

# App core
touch app/__init__.py
touch app/config.py
touch app/routes.py

# Services
touch app/services/__init__.py
touch app/services/preprocess.py
touch app/services/context.py
touch app/services/prompt.py
touch app/services/llm.py
touch app/services/parser.py
touch app/services/generator.py

# Models
touch app/models/__init__.py
touch app/models/objective.py

# Database
touch app/database/__init__.py
touch app/database/db.py

# Utils
touch app/utils/__init__.py
touch app/utils/helpers.py

# Tests & scripts
touch tests/test_pipeline.py
touch scripts/setup_db.py

# Notebook
touch notebooks/experiment.ipynb

# =========================
# DEFAULT CONTENT
# =========================

# run.py
cat <<EOL > run.py
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
EOL

# app/__init__.py
cat <<EOL > app/__init__.py
from flask import Flask

def create_app():
    app = Flask(__name__)

    from app.routes import main
    app.register_blueprint(main)

    return app
EOL

# app/routes.py
cat <<EOL > app/routes.py
from flask import Blueprint, request, jsonify
from app.services.generator import ObjectiveGeneratorPipeline

main = Blueprint("main", __name__)

@main.route("/generate", methods=["POST"])
def generate():
    data = request.json

    pipeline = ObjectiveGeneratorPipeline(
        bsc=data.get("bsc"),
        position=data.get("position"),
        jd=data.get("job_description"),
        n=data.get("num_objectives", 3)
    )

    result = pipeline.run()

    return jsonify(result)
EOL

# requirements.txt
cat <<EOL > requirements.txt
flask
ollama
python-dotenv
EOL

# .gitignore
cat <<EOL > .gitignore
.env
__pycache__/
*.pyc
EOL

# README.md
cat <<EOL > README.md
# AI Objective Generator

Generate SMART objectives using:
- BSC
- Role
- Job Description

Powered by Ollama (free local LLM).
EOL

# =========================
# GIT COMMANDS
# =========================

echo "📦 Adding files to git..."
git add .

echo "📝 Committing..."
git commit -m "Initial project structure with modular pipeline"

echo "⬆️ Pushing to GitHub..."
git push origin main

echo "✅ DONE! Project pushed successfully."