import json
from flask import Flask, request, jsonify, send_from_directory
from predict_fights_alpha import predict_fight
from ml_web import main
from testing.testing_time_period import process_dates
import os
import subprocess
import pandas as pd
from flask_cors import CORS
import sys
import csv
import base64
import time

app = Flask(__name__)
CORS(app)

@app.route('/get_all_fighter_names', methods=['GET'])
def get_all_fighter_names():
    csv_file_path = os.path.join('data', 'detailed_fighter_stats.csv')
    data = read_csv(csv_file_path)
    fighter_names = []
    for row in data:
        fighter_names.append(row['Fighter'])
    # print(fighter_names)
    return jsonify(fighter_names)

@app.route("/predict", methods=["POST"])
def predict():
    data = request.json
    fighter_name1 = data.get("fighter_name1")
    fighter_name2 = data.get("fighter_name2")
    print(fighter_name1, fighter_name2)

    if os.environ.get("FLASK_APP") != "app":
        os.environ["FLASK_APP"] = "app"

    # predict_fihts_alpha 
    predict_fight(fighter_name1, fighter_name2)
    # ml_web
    main()

    response = {"message": "Fighter stats processed"}
    return jsonify(response)

# @app.route("/train", methods=["POST"])
# def train():
#     try:
#         main()
#         response = {"message": "Model trained successfully"}
#     except Exception as e:
#         response = {"message": f"Error during training: {e}"}

#     return jsonify(response)

def read_csv(file_path):
    data = []
    with open(file_path, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            data.append(row)
    return data

@app.route('/get_stats', methods=['POST'])
def get_stats():
    data = request.json
    fighter_name1 = data.get("fighter_name1")
    fighter_name2 = data.get("fighter_name2")
    print(fighter_name1, fighter_name2)

    csv_file_path = os.path.join('data', 'detailed_fighter_stats.csv')
    data = read_csv(csv_file_path)

    fighter1_stats = {}
    fighter2_stats = {}
    for row in data:
        if row['Fighter'] == fighter_name1:
            fighter1_stats = row
        if row['Fighter'] == fighter_name2:
            fighter2_stats = row

    response = {
        "fighter1_stats": fighter1_stats,
        "fighter2_stats": fighter2_stats
    }
    
    return jsonify(response)

    
@app.route("/get_predicted_data", methods=["GET"])
def get_predicted_data():
    try:
        with open(os.path.join("data", "predicted_data.json"), "r") as json_file:
            predicted_data_dict = json.load(json_file)
        response = {
            "predicted_data": predicted_data_dict["predict_data"],
            "class_probabilities": predicted_data_dict["class_probabilities"],
        }
    except FileNotFoundError:
        response = {"message": "Predicted data not found"}
    
    return jsonify(response)

def get_test_results():
    file_path = os.path.join('test_results', 'testing_time_period.txt')
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
        strategy = data.get("strategy")
        process_dates(testFrom_card, testTo_card, strategy)

        response = get_test_results()
    except Exception as e:
        response = {"message": f"Error during testing: {e}"}

    return jsonify(response)

@app.route('/get_bankroll_plot', methods=['GET'])
def get_bankroll_plot():
    with open(os.path.join("data", "bankroll_plot.png"), "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
    return {"image": encoded_image}

@app.route('/get_predictions_plot', methods=['GET'])
def get_predictions_plot():
    with open(os.path.join("data", "predictions_bankroll_plot.png"), "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
    return {"image": encoded_image}

# test to see if flask is running
@app.route("/test_flask", methods=["GET"])
def test_flask():
    return {"message": "Flask is running"}

if __name__ == "__main__":
    app.run(debug=True)
