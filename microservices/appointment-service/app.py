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

logger = logging.getLogger("appointment-service")


# -------------------------
# Prometheus metrics
# -------------------------

REQUEST_COUNT = Counter(
    "appointment_service_requests_total",
    "Total number of requests received by appointment service"
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
        "service": "appointment-service"
    })


# -------------------------
# Appointment API
# -------------------------

@app.route("/appointments")
def appointments():
    REQUEST_COUNT.inc()

    logger.info("Fetching appointment list")

    appointment_data = [
        {
            "id": 1,
            "patient_id": 1,
            "doctor": "Dr. Smith",
            "date": "2026-10-01",
            "status": "confirmed"
        },
        {
            "id": 2,
            "patient_id": 2,
            "doctor": "Dr. Williams",
            "date": "2026-10-02",
            "status": "scheduled"
        }
    ]

    return jsonify({
        "appointments": appointment_data
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
    logger.info("Starting appointment-service")

    app.run(
        host="0.0.0.0",
        port=5002
    )