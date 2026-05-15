from pathlib import Path
import json
import ollama

from .prompt_builder import build_prompt


def generate(num_objectives: int = 5):
    context_path = Path("Data/processed/retrieved_context.json")

    with open(context_path, "r", encoding="utf-8") as f:
        context = json.load(f)

    prompt = build_prompt(context, num_objectives)

    response = ollama.chat(
        model="llama3",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    output = response["message"]["content"]

    save_path = Path("Data/processed/generated_objectives.json")

    with open(save_path, "w", encoding="utf-8") as f:
        f.write(output)
    print(output)
    print(f"\n✅ Saved: {save_path}")


if __name__ == "__main__":
    generate(5)