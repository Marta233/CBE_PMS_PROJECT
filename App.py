import os
from flask import Flask, render_template, request, jsonify
# from scripts.preprocess import extract_bsc_context, extract_jd_context
# from scripts.prompt import build_smart_objective_prompt
# from scripts.llm import generate_objectives
app = Flask(__name__)
@app.route('/')
def index():
    return render_template('index.html')
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)