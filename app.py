import json
from flask import Flask, request, jsonify
from oldModel.predict_fights_elo import process
from oldModel.ml_training_duplication import lgbm
from oldModel.testing import runTests
import os
import subprocess
import pandas as pd
from flask_cors import CORS
import sys
import csv
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
        lgbm()
        response = {"message": "Model trained successfully"}
    except Exception as e:
        response = {"message": f"Error during training: {e}"}

    return jsonify(response)

def read_csv(file_path):
    data = []
    with open(file_path, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            data.append(row)
    return data

@app.route('/get_stats', methods=['GET'])
def get_stats():
    csv_file_path = os.path.join('oldModel', 'predict_fights_elo.csv')
    data = read_csv(csv_file_path)
    return jsonify(data)
    

@app.route("/get_predicted_data", methods=["GET"])
def get_predicted_data():
    try:
        with open(os.path.join("oldModel", "predicted_data.json"), "r") as json_file:
            predicted_data_dict = json.load(json_file)
        response = {
            "predicted_data": predicted_data_dict["predict_data"],
            "class_probabilities": predicted_data_dict["class_probabilities"],
        }
    except FileNotFoundError:
        response = {"message": "Predicted data not found"}
    
    return jsonify(response)

def get_test_results():
    file_path = os.path.join('oldModel', 'testing.txt')
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        return {'content': content}
    except FileNotFoundError:
        return {'error': 'File not found'}, 404

@app.route("/test", methods=["POST"])
def test():
    try:
        data = request.json
        testFrom_card = data.get("testFrom_card")
        testTo_card = data.get("testTo_card")
        runTests(testFrom_card, testTo_card)

        response = get_test_results()
    except Exception as e:
        response = {"message": f"Error during testing: {e}"}

    return jsonify(response)

if __name__ == "__main__":
    app.run(debug=True)
