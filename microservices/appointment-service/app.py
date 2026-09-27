from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import sqlite3
import logging
import requests
import time

app = Flask(__name__)

# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

logger = logging.getLogger("appointment-service")

# --------------------------------------------------
# Service URLs
# --------------------------------------------------

PATIENT_SERVICE_URL = "http://patient-service:5001"
BILLING_SERVICE_URL = "http://billing-service:5003"

# --------------------------------------------------
# Prometheus Metrics
# --------------------------------------------------

REQUEST_COUNT = Counter(
    "appointment_service_requests_total",
    "Total number of requests received by appointment service"
)

ERROR_COUNT = Counter(
    "appointment_service_errors_total",
    "Total number of errors in appointment service"
)

REQUEST_DURATION = Histogram(
    "appointment_service_request_duration_seconds",
    "Request duration in seconds"
)

PATIENT_SERVICE_ERRORS = Counter(
    "appointment_patient_service_errors_total",
    "Total number of failed calls to patient service"
)

BILLING_SERVICE_ERRORS = Counter(
    "appointment_billing_service_errors_total",
    "Total number of failed calls to billing service"
)

# --------------------------------------------------
# Database
# --------------------------------------------------

DATABASE = "appointments.db"


def get_db_connection():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():

    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed',
            bill_id INTEGER
        )
    """)

    connection.commit()

    connection.close()

    logger.info("Appointment database initialized")


# --------------------------------------------------
# Health
# --------------------------------------------------

@app.route("/health", methods=["GET"])
def health():

    REQUEST_COUNT.inc()

    return jsonify({
        "status": "healthy",
        "service": "appointment-service"
    })


# --------------------------------------------------
# Get All Appointments
# --------------------------------------------------

@app.route("/appointments", methods=["GET"])
def get_appointments():

    start_time = time.time()
    REQUEST_COUNT.inc()

    try:

        logger.info("Fetching all appointments")

        connection = get_db_connection()

        appointments = connection.execute(
            "SELECT * FROM appointments"
        ).fetchall()

        connection.close()

        appointment_list = [
            dict(appointment)
            for appointment in appointments
        ]

        logger.info(
            "Successfully fetched %s appointments",
            len(appointment_list)
        )

        return jsonify({
            "appointments": appointment_list
        })

    except Exception as error:

        ERROR_COUNT.inc()

        logger.exception(
            "Failed to fetch appointments: %s",
            error
        )

        return jsonify({
            "error": "Unable to fetch appointments"
        }), 500

    finally:

        REQUEST_DURATION.observe(
            time.time() - start_time
        )


# --------------------------------------------------
# Get Appointment By ID
# --------------------------------------------------

@app.route("/appointments/<int:appointment_id>", methods=["GET"])
def get_appointment(appointment_id):

    start_time = time.time()
    REQUEST_COUNT.inc()

    try:

        logger.info(
            "Fetching appointment appointment_id=%s",
            appointment_id
        )

        connection = get_db_connection()

        appointment = connection.execute(
            "SELECT * FROM appointments WHERE id = ?",
            (appointment_id,)
        ).fetchone()

        connection.close()

        if appointment is None:

            logger.warning(
                "Appointment not found appointment_id=%s",
                appointment_id
            )

            return jsonify({
                "error": "Appointment not found"
            }), 404

        return jsonify({
            "appointment": dict(appointment)
        })

    except Exception as error:

        ERROR_COUNT.inc()

        logger.exception(
            "Failed to fetch appointment: %s",
            error
        )

        return jsonify({
            "error": "Unable to fetch appointment"
        }), 500

    finally:

        REQUEST_DURATION.observe(
            time.time() - start_time
        )


# --------------------------------------------------
# Create Appointment
# --------------------------------------------------

@app.route("/appointments", methods=["POST"])
def create_appointment():

    start_time = time.time()
    REQUEST_COUNT.inc()

    try:

        data = request.get_json()

        if not data:

            logger.warning(
                "Create appointment request has no JSON body"
            )

            return jsonify({
                "error": "Request body is required"
            }), 400

        required_fields = [
            "patient_id",
            "doctor",
            "date"
        ]

        for field in required_fields:

            if field not in data:

                logger.warning(
                    "Missing required field=%s",
                    field
                )

                return jsonify({
                    "error": f"{field} is required"
                }), 400

        patient_id = data["patient_id"]
        doctor = data["doctor"]
        appointment_date = data["date"]

        logger.info(
            "Appointment request received patient_id=%s doctor=%s date=%s",
            patient_id,
            doctor,
            appointment_date
        )

        # --------------------------------------------------
        # Step 1: Check Patient Service
        # --------------------------------------------------

        logger.info(
            "Checking patient patient_id=%s",
            patient_id
        )

        try:

            patient_response = requests.get(
                f"{PATIENT_SERVICE_URL}/patients/{patient_id}",
                timeout=3
            )

        except requests.RequestException as error:

            PATIENT_SERVICE_ERRORS.inc()
            ERROR_COUNT.inc()

            logger.error(
                "Patient service unavailable: %s",
                error
            )

            return jsonify({
                "error": "Patient service unavailable"
            }), 503

        if patient_response.status_code == 404:

            logger.warning(
                "Patient does not exist patient_id=%s",
                patient_id
            )

            return jsonify({
                "error": "Patient not found"
            }), 404

        if not patient_response.ok:

            PATIENT_SERVICE_ERRORS.inc()
            ERROR_COUNT.inc()

            logger.error(
                "Patient service returned status=%s",
                patient_response.status_code
            )

            return jsonify({
                "error": "Unable to validate patient"
            }), 503

        patient_data = patient_response.json()["patient"]

        logger.info(
            "Patient found patient_id=%s name=%s",
            patient_id,
            patient_data["name"]
        )

        # --------------------------------------------------
        # Step 2: Create Billing Record
        # --------------------------------------------------

        logger.info(
            "Creating billing record patient_id=%s",
            patient_id
        )

        billing_payload = {
            "patient_id": patient_id,
            "amount": 250.00,
            "currency": "GBP"
        }

        try:

            billing_response = requests.post(
                f"{BILLING_SERVICE_URL}/bills",
                json=billing_payload,
                timeout=3
            )

        except requests.RequestException as error:

            BILLING_SERVICE_ERRORS.inc()
            ERROR_COUNT.inc()

            logger.error(
                "Billing service unavailable: %s",
                error
            )

            return jsonify({
                "error": "Billing service unavailable"
            }), 503

        if not billing_response.ok:

            BILLING_SERVICE_ERRORS.inc()
            ERROR_COUNT.inc()

            logger.error(
                "Billing service returned status=%s",
                billing_response.status_code
            )

            return jsonify({
                "error": "Unable to create billing record"
            }), 503

        billing_data = billing_response.json()["bill"]

        bill_id = billing_data["id"]

        logger.info(
            "Billing record created bill_id=%s patient_id=%s",
            bill_id,
            patient_id
        )

        # --------------------------------------------------
        # Step 3: Create Appointment
        # --------------------------------------------------

        connection = get_db_connection()

        cursor = connection.execute("""
            INSERT INTO appointments
            (patient_id, doctor, appointment_date, status, bill_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            patient_id,
            doctor,
            appointment_date,
            "confirmed",
            bill_id
        ))

        connection.commit()

        appointment_id = cursor.lastrowid

        connection.close()

        logger.info(
            "Appointment created appointment_id=%s patient_id=%s",
            appointment_id,
            patient_id
        )

        # --------------------------------------------------
        # Step 4: Return Combined Response
        # --------------------------------------------------

        logger.info(
            "Appointment request completed appointment_id=%s",
            appointment_id
        )

        return jsonify({
            "message": "Appointment created successfully",
            "appointment": {
                "id": appointment_id,
                "patient_id": patient_id,
                "patient_name": patient_data["name"],
                "doctor": doctor,
                "date": appointment_date,
                "status": "confirmed",
                "bill": {
                    "id": bill_id,
                    "amount": billing_data["amount"],
                    "currency": billing_data["currency"],
                    "status": billing_data["status"]
                }
            }
        }), 201

    except Exception as error:

        ERROR_COUNT.inc()

        logger.exception(
            "Failed to create appointment: %s",
            error
        )

        return jsonify({
            "error": "Unable to create appointment"
        }), 500

    finally:

        REQUEST_DURATION.observe(
            time.time() - start_time
        )


# --------------------------------------------------
# Delete Appointment
# --------------------------------------------------

@app.route("/appointments/<int:appointment_id>", methods=["DELETE"])
def delete_appointment(appointment_id):

    start_time = time.time()
    REQUEST_COUNT.inc()

    try:

        logger.info(
            "Deleting appointment appointment_id=%s",
            appointment_id
        )

        connection = get_db_connection()

        appointment = connection.execute(
            "SELECT * FROM appointments WHERE id = ?",
            (appointment_id,)
        ).fetchone()

        if appointment is None:

            connection.close()

            logger.warning(
                "Appointment not found appointment_id=%s",
                appointment_id
            )

            return jsonify({
                "error": "Appointment not found"
            }), 404

        connection.execute(
            "DELETE FROM appointments WHERE id = ?",
            (appointment_id,)
        )

        connection.commit()

        connection.close()

        logger.info(
            "Appointment deleted appointment_id=%s",
            appointment_id
        )

        return jsonify({
            "message": "Appointment deleted successfully",
            "appointment_id": appointment_id
        })

    except Exception as error:

        ERROR_COUNT.inc()

        logger.exception(
            "Failed to delete appointment: %s",
            error
        )

        return jsonify({
            "error": "Unable to delete appointment"
        }), 500

    finally:

        REQUEST_DURATION.observe(
            time.time() - start_time
        )


# --------------------------------------------------
# Metrics
# --------------------------------------------------

@app.route("/metrics", methods=["GET"])
def metrics():

    return Response(
        generate_latest(),
        mimetype=CONTENT_TYPE_LATEST
    )


# --------------------------------------------------
# Start Application
# --------------------------------------------------

if __name__ == "__main__":

    initialize_database()

    logger.info("Starting appointment-service")

    app.run(
        host="0.0.0.0",
        port=5002
    )