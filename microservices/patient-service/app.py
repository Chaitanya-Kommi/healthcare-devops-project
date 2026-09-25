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

logger = logging.getLogger("patient-service")


# -------------------------
# Prometheus metrics
# -------------------------

REQUEST_COUNT = Counter(
    "patient_service_requests_total",
    "Total number of requests received by patient service"
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
        "service": "patient-service"
    })


# -------------------------
# Patient API
# -------------------------

@app.route("/patients")
def patients():
    REQUEST_COUNT.inc()

    logger.info("Fetching patient list")

    patients_data = [
        {
            "id": 1,
            "name": "John Doe",
            "status": "active"
        },
        {
            "id": 2,
            "name": "Jane Smith",
            "status": "active"
        }
    ]

    return jsonify({
        "patients": patients_data
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
    logger.info("Starting patient-service")

    app.run(
        host="0.0.0.0",
        port=5001
    )
