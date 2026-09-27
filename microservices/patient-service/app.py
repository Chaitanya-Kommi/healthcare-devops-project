from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import sqlite3
import logging
import time

app = Flask(__name__)

# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

logger = logging.getLogger("patient-service")

# --------------------------------------------------
# Prometheus Metrics
# --------------------------------------------------

REQUEST_COUNT = Counter(
    "patient_service_requests_total",
    "Total number of requests received by patient service"
)

ERROR_COUNT = Counter(
    "patient_service_errors_total",
    "Total number of errors in patient service"
)

REQUEST_DURATION = Histogram(
    "patient_service_request_duration_seconds",
    "Request duration in seconds"
)

# --------------------------------------------------
# Database
# --------------------------------------------------

DATABASE = "patients.db"


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():

    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            phone TEXT,
            status TEXT NOT NULL DEFAULT 'active'
        )
    """)

    connection.commit()

    count = connection.execute(
        "SELECT COUNT(*) FROM patients"
    ).fetchone()[0]

    if count == 0:

        connection.execute("""
            INSERT INTO patients
            (name, age, gender, phone, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "John Doe",
            45,
            "Male",
            "07123456789",
            "active"
        ))

        connection.execute("""
            INSERT INTO patients
            (name, age, gender, phone, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "Jane Smith",
            32,
            "Female",
            "07234567890",
            "active"
        ))

        connection.commit()

    connection.close()

    logger.info("Patient database initialized")


# --------------------------------------------------
# Health
# --------------------------------------------------

@app.route("/health", methods=["GET"])
def health():

    REQUEST_COUNT.inc()

    return jsonify({
        "status": "healthy",
        "service": "patient-service"
    })


# --------------------------------------------------
# Get All Patients
# --------------------------------------------------

@app.route("/patients", methods=["GET"])
def get_patients():

    start_time = time.time()
    REQUEST_COUNT.inc()

    try:

        logger.info("Fetching all patients")

        connection = get_db_connection()

        patients = connection.execute(
            "SELECT * FROM patients"
        ).fetchall()

        connection.close()

        patient_list = [
            dict(patient)
            for patient in patients
        ]

        logger.info(
            "Successfully fetched %s patients",
            len(patient_list)
        )

        return jsonify({
            "patients": patient_list
        })

    except Exception as error:

        ERROR_COUNT.inc()

        logger.exception(
            "Failed to fetch patients: %s",
            error
        )

        return jsonify({
            "error": "Unable to fetch patients"
        }), 500

    finally:

        REQUEST_DURATION.observe(
            time.time() - start_time
        )


# --------------------------------------------------
# Get Patient By ID
# --------------------------------------------------

@app.route("/patients/<int:patient_id>", methods=["GET"])
def get_patient(patient_id):

    start_time = time.time()
    REQUEST_COUNT.inc()

    try:

        logger.info(
            "Fetching patient patient_id=%s",
            patient_id
        )

        connection = get_db_connection()

        patient = connection.execute(
            "SELECT * FROM patients WHERE id = ?",
            (patient_id,)
        ).fetchone()

        connection.close()

        if patient is None:

            logger.warning(
                "Patient not found patient_id=%s",
                patient_id
            )

            return jsonify({
                "error": "Patient not found"
            }), 404

        logger.info(
            "Patient found patient_id=%s",
            patient_id
        )

        return jsonify({
            "patient": dict(patient)
        })

    except Exception as error:

        ERROR_COUNT.inc()

        logger.exception(
            "Failed to fetch patient patient_id=%s",
            patient_id
        )

        return jsonify({
            "error": "Unable to fetch patient"
        }), 500

    finally:

        REQUEST_DURATION.observe(
            time.time() - start_time
        )


# --------------------------------------------------
# Create Patient
# --------------------------------------------------

@app.route("/patients", methods=["POST"])
def create_patient():

    start_time = time.time()
    REQUEST_COUNT.inc()

    try:

        data = request.get_json()

        if not data:

            logger.warning(
                "Create patient request has no JSON body"
            )

            return jsonify({
                "error": "Request body is required"
            }), 400

        required_fields = [
            "name",
            "age",
            "gender"
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

        connection = get_db_connection()

        cursor = connection.execute("""
            INSERT INTO patients
            (name, age, gender, phone, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data["name"],
            data["age"],
            data["gender"],
            data.get("phone"),
            "active"
        ))

        connection.commit()

        patient_id = cursor.lastrowid

        connection.close()

        logger.info(
            "Patient created patient_id=%s name=%s",
            patient_id,
            data["name"]
        )

        return jsonify({
            "message": "Patient created successfully",
            "patient": {
                "id": patient_id,
                "name": data["name"],
                "age": data["age"],
                "gender": data["gender"],
                "phone": data.get("phone"),
                "status": "active"
            }
        }), 201

    except Exception as error:

        ERROR_COUNT.inc()

        logger.exception(
            "Failed to create patient: %s",
            error
        )

        return jsonify({
            "error": "Unable to create patient"
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

    logger.info("Starting patient-service")

    app.run(
        host="0.0.0.0",
        port=5001
    )