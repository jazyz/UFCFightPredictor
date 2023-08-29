import json
from flask import Flask, request, jsonify
from predict_fight_outcomes import process
import os
import subprocess
import pandas as pd
from flask_cors import CORS
import sys
app = Flask(__name__)
CORS(app)

@app.route("/predict", methods=["POST"])
def predict():
    data = request.json
    fighter_name1 = data.get("fighter_name1")
    fighter_name2 = data.get("fighter_name2")
    print(fighter_name1, fighter_name2)

    if os.environ.get("FLASK_APP") != "app":
        os.environ["FLASK_APP"] = "app"

    process(fighter_name1, fighter_name2)

    response = {"message": "Fighter stats processed"}
    return jsonify(response)

@app.route("/train", methods=["POST"])
def train():
    try:
        venv_python_executable = sys.executable
        subprocess.run([venv_python_executable, "ml_training_dynamic.py"], check=True)
        response = {"message": "Model trained successfully"}
    except subprocess.CalledProcessError as e:
        response = {"message": f"Error during training: {e}"}
    
    return jsonify(response)

@app.route("/get_stats", methods=["GET"])
def get_stats():
    try:
        # get stats from the csv file
        stats = pd.read_csv("predict_fights.csv")
        response = {"stats": stats.to_dict(orient="records")}
    except FileNotFoundError:
        response = {"message": "Fighters data not found"}
    
    return jsonify(response)

@app.route("/get_predicted_data", methods=["GET"])
def get_predicted_data():
    try:
        with open("predicted_data.json", "r") as json_file:
            predicted_data_dict = json.load(json_file)
        response = {
            "predicted_data": predicted_data_dict["predict_data"],
            "class_probabilities": predicted_data_dict["class_probabilities"],
        }
    except FileNotFoundError:
        response = {"message": "Predicted data not found"}
    
    return jsonify(response)

if __name__ == "__main__":
    app.run()
