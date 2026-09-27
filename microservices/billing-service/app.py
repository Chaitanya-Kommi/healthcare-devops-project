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

logger = logging.getLogger("billing-service")

# --------------------------------------------------
# Prometheus Metrics
# --------------------------------------------------

REQUEST_COUNT = Counter(
    "billing_service_requests_total",
    "Total number of requests received by billing service"
)

ERROR_COUNT = Counter(
    "billing_service_errors_total",
    "Total number of errors in billing service"
)

REQUEST_DURATION = Histogram(
    "billing_service_request_duration_seconds",
    "Request duration in seconds"
)

# --------------------------------------------------
# Database
# --------------------------------------------------

DATABASE = "billing.db"


def get_db_connection():

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():

    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'GBP',
            status TEXT NOT NULL DEFAULT 'pending'
        )
    """)

    connection.commit()

    count = connection.execute(
        "SELECT COUNT(*) FROM bills"
    ).fetchone()[0]

    if count == 0:

        connection.execute("""
            INSERT INTO bills
            (patient_id, amount, currency, status)
            VALUES (?, ?, ?, ?)
        """, (
            1,
            250.00,
            "GBP",
            "paid"
        ))

        connection.execute("""
            INSERT INTO bills
            (patient_id, amount, currency, status)
            VALUES (?, ?, ?, ?)
        """, (
            2,
            180.50,
            "GBP",
            "pending"
        ))

        connection.commit()

    connection.close()

    logger.info("Billing database initialized")


# --------------------------------------------------
# Health
# --------------------------------------------------

@app.route("/health", methods=["GET"])
def health():

    REQUEST_COUNT.inc()

    return jsonify({
        "status": "healthy",
        "service": "billing-service"
    })


# --------------------------------------------------
# Get Bills For Patient
# --------------------------------------------------

@app.route("/bills/patient/<int:patient_id>", methods=["GET"])
def get_patient_bills(patient_id):

    start_time = time.time()
    REQUEST_COUNT.inc()

    try:

        logger.info(
            "Fetching bills patient_id=%s",
            patient_id
        )

        connection = get_db_connection()

        bills = connection.execute("""
            SELECT *
            FROM bills
            WHERE patient_id = ?
        """, (
            patient_id,
        )).fetchall()

        connection.close()

        bill_list = [
            dict(bill)
            for bill in bills
        ]

        logger.info(
            "Found %s bills patient_id=%s",
            len(bill_list),
            patient_id
        )

        return jsonify({
            "patient_id": patient_id,
            "bills": bill_list
        })

    except Exception as error:

        ERROR_COUNT.inc()

        logger.exception(
            "Failed to fetch bills patient_id=%s: %s",
            patient_id,
            error
        )

        return jsonify({
            "error": "Unable to fetch bills"
        }), 500

    finally:

        REQUEST_DURATION.observe(
            time.time() - start_time
        )


# --------------------------------------------------
# Create Bill
# --------------------------------------------------

@app.route("/bills", methods=["POST"])
def create_bill():

    start_time = time.time()
    REQUEST_COUNT.inc()

    try:

        data = request.get_json()

        if not data:

            logger.warning(
                "Create bill request has no JSON body"
            )

            return jsonify({
                "error": "Request body is required"
            }), 400

        required_fields = [
            "patient_id",
            "amount"
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
        amount = data["amount"]
        currency = data.get("currency", "GBP")

        connection = get_db_connection()

        cursor = connection.execute("""
            INSERT INTO bills
            (patient_id, amount, currency, status)
            VALUES (?, ?, ?, ?)
        """, (
            patient_id,
            amount,
            currency,
            "pending"
        ))

        connection.commit()

        bill_id = cursor.lastrowid

        connection.close()

        logger.info(
            "Bill created bill_id=%s patient_id=%s amount=%s %s",
            bill_id,
            patient_id,
            amount,
            currency
        )

        return jsonify({
            "message": "Bill created successfully",
            "bill": {
                "id": bill_id,
                "patient_id": patient_id,
                "amount": amount,
                "currency": currency,
                "status": "pending"
            }
        }), 201

    except Exception as error:

        ERROR_COUNT.inc()

        logger.exception(
            "Failed to create bill: %s",
            error
        )

        return jsonify({
            "error": "Unable to create bill"
        }), 500

    finally:

        REQUEST_DURATION.observe(
            time.time() - start_time
        )


# --------------------------------------------------
# Pay Bill
# --------------------------------------------------

@app.route("/bills/<int:bill_id>/pay", methods=["PUT"])
def pay_bill(bill_id):

    start_time = time.time()
    REQUEST_COUNT.inc()

    try:

        logger.info(
            "Payment requested bill_id=%s",
            bill_id
        )

        connection = get_db_connection()

        bill = connection.execute(
            "SELECT * FROM bills WHERE id = ?",
            (bill_id,)
        ).fetchone()

        if bill is None:

            connection.close()

            logger.warning(
                "Bill not found bill_id=%s",
                bill_id
            )

            return jsonify({
                "error": "Bill not found"
            }), 404

        if bill["status"] == "paid":

            connection.close()

            logger.info(
                "Bill already paid bill_id=%s",
                bill_id
            )

            return jsonify({
                "message": "Bill is already paid",
                "bill": dict(bill)
            })

        connection.execute("""
            UPDATE bills
            SET status = ?
            WHERE id = ?
        """, (
            "paid",
            bill_id
        ))

        connection.commit()

        updated_bill = connection.execute(
            "SELECT * FROM bills WHERE id = ?",
            (bill_id,)
        ).fetchone()

        connection.close()

        logger.info(
            "Bill payment successful bill_id=%s",
            bill_id
        )

        return jsonify({
            "message": "Payment successful",
            "bill": dict(updated_bill)
        })

    except Exception as error:

        ERROR_COUNT.inc()

        logger.exception(
            "Payment failed bill_id=%s: %s",
            bill_id,
            error
        )

        return jsonify({
            "error": "Payment failed"
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

    logger.info("Starting billing-service")

    app.run(
        host="0.0.0.0",
        port=5003
    )
