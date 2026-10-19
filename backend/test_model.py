
from app.predictor import predict_news

sample = """
The government announced a new public transport initiative
after reviewing proposals from local authorities.
"""

result = predict_news(sample)

print("Prediction:", result["label"])
print("Confidence:", result["confidence"], "%")
