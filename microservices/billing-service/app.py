from flask import Flask, jsonify, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
import logging

app = Flask(__name__)

# -------------------------
# Logging configuration
# -------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

logger = logging.getLogger("billing-service")


# -------------------------
# Prometheus metrics
# -------------------------

REQUEST_COUNT = Counter(
    "billing_service_requests_total",
    "Total number of requests received by billing service"
)


# -------------------------
# Health check
# -------------------------

@app.route("/health")
def health():
    REQUEST_COUNT.inc()

    logger.info("Health check requested")

    return jsonify({
        "status": "healthy",
        "service": "billing-service"
    })


# -------------------------
# Billing API
# -------------------------

@app.route("/bills")
def bills():
    REQUEST_COUNT.inc()

    logger.info("Fetching billing information")

    billing_data = [
        {
            "id": 1,
            "patient_id": 1,
            "amount": 250.00,
            "currency": "GBP",
            "status": "paid"
        },
        {
            "id": 2,
            "patient_id": 2,
            "amount": 180.50,
            "currency": "GBP",
            "status": "pending"
        }
    ]

    return jsonify({
        "bills": billing_data
    })


# -------------------------
# Prometheus metrics
# -------------------------

@app.route("/metrics")
def metrics():
    return Response(
        generate_latest(),
        mimetype=CONTENT_TYPE_LATEST
    )


# -------------------------
# Start application
# -------------------------

if __name__ == "__main__":
    logger.info("Starting billing-service")

    app.run(
        host="0.0.0.0",
        port=5003
    )