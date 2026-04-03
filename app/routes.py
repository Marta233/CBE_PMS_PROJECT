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
