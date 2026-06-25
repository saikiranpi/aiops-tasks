from flask import Flask, request, jsonify
import pickle
import os

app = Flask(__name__)
# The model is baked into the image during the CI phase
model = pickle.load(open('model/fraud_model.pkl', 'rb'))

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json['features']
    prediction = model.predict([data])
    return jsonify({"fraud_probability": float(prediction[0])})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
