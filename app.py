"""Web layer (Flask). Serves the page and a small JSON API. All maths lives in index_builder/."""
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from index_builder import METHODS, DataLoader, IndexBuilder, IndexValidationError

DATA_DIR = Path(__file__).resolve().parent / "data"

# First run convenience: create the dummy data if it isn't there yet.
if not (DATA_DIR / "prices.csv").exists():
    subprocess.run([sys.executable, str(DATA_DIR / "generate_data.py")], check=True)

app = Flask(__name__)
loader = DataLoader(DATA_DIR)      # data is read once at start-up and cached in memory
builder = IndexBuilder(loader)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/universe")
def universe():
    first, last = loader.date_range
    methods = [{"key": k, "label": v} for k, v in METHODS.items()]   # list keeps the display order
    return jsonify(stocks=loader.universe(), methods=methods,
                   date_range={"min": f"{first:%Y-%m-%d}", "max": f"{last:%Y-%m-%d}"})


@app.post("/api/generate")
def generate():
    try:
        return jsonify(builder.build(request.get_json(silent=True)))
    except IndexValidationError as exc:          # user-fixable problem -> 400 with the reasons
        return jsonify(ok=False, **exc.report.to_dict()), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
