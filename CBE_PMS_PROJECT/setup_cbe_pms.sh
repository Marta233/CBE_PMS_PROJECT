#!/bin/bash

echo "🚀 Setting up CBE PMS RAG Project..."

# Project name
PROJECT_NAME="CBE_PMS_PROJECT"

# Create folder structure
echo "📁 Creating project structure..."
mkdir -p $PROJECT_NAME/{data/{raw,processed,external},notebooks,src/{ingestion,embeddings,retrieval,llm,pipeline,api,utils,config},tests,scripts}

# Create __init__.py files
echo "📦 Initializing Python modules..."
touch $PROJECT_NAME/src/__init__.py
find $PROJECT_NAME/src -type d -exec touch {}/__init__.py \;

# Create base files
echo "📝 Creating base files..."
touch $PROJECT_NAME/README.md
touch $PROJECT_NAME/requirements.txt
touch $PROJECT_NAME/.env
touch $PROJECT_NAME/.gitignore
touch $PROJECT_NAME/main.py

# Create script files
touch $PROJECT_NAME/scripts/run_ingestion.py
touch $PROJECT_NAME/scripts/build_index.py
touch $PROJECT_NAME/scripts/run_pipeline.py

# Create config files
touch $PROJECT_NAME/src/config/settings.yaml
touch $PROJECT_NAME/src/config/prompts.yaml

# Create virtual environment
echo "🐍 Creating virtual environment..."
python3 -m venv $PROJECT_NAME/venv

# Activate environment
source $PROJECT_NAME/venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "📦 Installing dependencies..."
pip install langchain langchain-community faiss-cpu chromadb python-dotenv flask

# Save dependencies
pip freeze > $PROJECT_NAME/requirements.txt

echo "✅ Setup complete!"
echo "👉 Project: $PROJECT_NAME"
echo "👉 Activate env: source $PROJECT_NAME/venv/bin/activate"
echo "👉 Run project: python main.py"