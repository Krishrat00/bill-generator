from flask import Flask, render_template, request, jsonify, send_file, session, redirect
import io, json, os, re, time
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from bill_template import generate_invoice
from data_manager import DatabaseManager, normalize_gstin, normalize_pincode, normalize_text
from db import DB_BACKEND, get_collection

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecret")
data_manager = DatabaseManager()

ADMIN_USER = os.environ.get("ADMIN_USER")
ADMIN_PASS = os.environ.get("ADMIN_PASS")
location_cache = {}
last_location_request = 0.0

# ---------- Routes ----------
@app.route("/")
def form():
    parties = data_manager.get_all_parties()
    transports = data_manager.get_all_transports()
    return render_template("form.html", parties=parties, transports=transports)

@app.route("/get_party_details")
def get_party_details():
    name = request.args.get("name")
    party = data_manager.get_party(name)
    if not party:
        return jsonify({"gstin": "", "place": "", "fixed_place": False})
    return jsonify(party)

@app.route("/get_transport_details")
def get_transport_details():
    name = request.args.get("name")
    transport = data_manager.get_transport(name)
    if not transport:
        return jsonify({"gstin": ""})
    return jsonify(transport)

@app.route("/save_city")
def save_city():
    city = normalize_text(request.args.get("city", ""))
    state = normalize_text(request.args.get("state", ""))
    pincode = normalize_pincode(request.args.get("pincode", ""))
    data_manager.add_city(city, state, pincode)
    return jsonify({"status": "ok"})

@app.route("/lookup_pincode")
def lookup_pincode():
    pincode = normalize_pincode(request.args.get("pincode", ""))
    if len(pincode) != 6:
        return jsonify({"place": "", "pincode": pincode}), 400
    try:
        with urlopen(f"https://api.postalpincode.in/pincode/{pincode}", timeout=8) as response:
            result = json.load(response)
    except Exception:
        return jsonify({"place": "", "pincode": pincode}), 502
    if not result or result[0].get("Status") != "Success" or not result[0].get("PostOffice"):
        return jsonify({"place": "", "pincode": pincode}), 404
    office = result[0]["PostOffice"][0]
    name = normalize_text(office.get("Name", ""))
    district = normalize_text(office.get("District", ""))
    state = normalize_text(office.get("State", ""))
    details = [part for part in (district, state) if part]
    place = f"{name} ({', '.join(details)})" if name and details else name or ", ".join(details)
    return jsonify({
        "name": name,
        "district": district,
        "state": state,
        "place": place,
        "pincode": pincode,
    })

@app.route("/search_location")
def search_location():
    query = request.args.get("q", "").strip()
    if len(query) < 3:
        return jsonify([])

    cache_key = query.casefold()
    cached = location_cache.get(cache_key)
    if cached and time.time() - cached["created"] < 600:
        return jsonify(cached["data"])

    global last_location_request
    elapsed = time.time() - last_location_request
    if elapsed < 1:
        return jsonify([]), 429

    params = urlencode({
        "countrycodes": "in",
        "q": query,
        "format": "json",
        "addressdetails": "1",
        "limit": "5",
    })
    request_url = f"https://nominatim.openstreetmap.org/search?{params}"
    upstream_request = Request(
        request_url,
        headers={"User-Agent": os.getenv("NOMINATIM_USER_AGENT", "bill-generator/1.0")},
    )
    try:
        last_location_request = time.time()
        with urlopen(upstream_request, timeout=8) as response:
            data = json.load(response)
            location_cache[cache_key] = {"created": time.time(), "data": data}
            return jsonify(data)
    except Exception:
        return jsonify([]), 502

@app.route("/add_pending", methods=["POST"])
def add_pending():
    data = request.get_json()
    data_manager.add_pending(
        type_=data["type"],
        name=data["name"],
        gstin=data.get("gstin", ""),
        place=data.get("place", ""),
        pincode=data.get("pincode", "")
    )
    return jsonify({"status": "ok"})

@app.route("/message")
def message_page():
    return render_template("message.html")

@app.route("/download", methods=["POST"])
def download():
    form = request.form
    for field in ["bill_no","date","customer_name","ch_no","gstin","transport"]:
        if not form.get(field):
            return f"{field} is required", 400

    try:
        formatted_date = datetime.strptime(form.get("date", ""), "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        formatted_date = form.get("date", "")

    data = {
        "invoice_no": form.get("bill_no", ""),
        "date": formatted_date,
        "party_name": normalize_text(form.get("customer_name", "")),
        "place": normalize_text(form.get("ch_no", "")),
        "pincode": normalize_pincode(form.get("pincode", "")),
        "party_gstin": format_gstin(form.get("gstin", "")),
        "transport": normalize_text(form.get("transport", "")),
        "transport_gstin": normalize_gstin(form.get("transport_gstin", "")),
        "units" : form.getlist('unit[]'),
        "items": []
    }

    print(data)

    for name, qty, unit, rate in zip(
        form.getlist("item_name[]"),
        form.getlist("qty[]"),
        form.getlist("unit[]"),
        form.getlist("rate[]")
    ):
        if name and qty and unit and rate:
            data["items"].append({
                "name": name,
                "qty": float(qty),
                "unit": unit,
                "rate": float(rate)
            })

    output = io.BytesIO()
    total = generate_invoice(data, output)
    data_manager.save_bill(data["invoice_no"], data, total)
    session['invoice_data'] = {
        "invoice_no": data["invoice_no"],
        "date": data["date"],
        "party_gstin": data["party_gstin"],
        "place": data["place"],
        "pin": data["pincode"],
        "total_value": total,
    }

    output.seek(0)
    filename = f"{data['invoice_no']}_ANANT_CREATION.pdf"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/pdf")

@app.route("/bills/<invoice_no>")
def get_bill(invoice_no):
    bill = data_manager.get_bill(invoice_no)
    if not bill:
        return jsonify({"error": "Bill not found"}), 404
    return jsonify(bill)

@app.route("/bills/recent")
def recent_bills():
    try:
        limit = request.args.get("limit", 20, type=int)
        return jsonify(data_manager.get_recent_bills(limit))
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400

@app.route("/admin/bills")
def admin_recent_bills():
    if not session.get("admin"):
        return jsonify({"error": "unauthorized"}), 401
    try:
        limit = request.args.get("limit", 50, type=int)
        return jsonify(data_manager.get_recent_bills(limit))
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400

@app.route("/admin/bills/<path:invoice_no>")
def admin_bill(invoice_no):
    if not session.get("admin"):
        return jsonify({"error": "unauthorized"}), 401
    bill = data_manager.get_bill(invoice_no)
    if not bill:
        return jsonify({"error": "Bill not found"}), 404
    return jsonify(bill)

# ---------- Admin ----------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            session["admin"] = True
            return redirect("/admin/pending")
        else:
            return "Invalid credentials", 403
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin/login")

@app.route("/admin/pending")
def admin_pending():
    if not session.get("admin"):
        return redirect("/admin/login")
    pending = data_manager.get_all_pending()
    return render_template("admin.html", pending=pending)

@app.route("/admin/analytics")
def admin_analytics():
    if not session.get("admin"):
        return redirect("/admin/login")

    today = datetime.now(timezone.utc).date()
    view = request.args.get("view", "month")
    if view not in {"month", "year"}:
        view = "month"
    try:
        selected_month = datetime.strptime(request.args.get("month", ""), "%Y-%m").date().replace(day=1)
    except ValueError:
        selected_month = today.replace(day=1)
    try:
        selected_year = int(request.args.get("year", today.year))
    except (TypeError, ValueError):
        selected_year = today.year
    if not 1 <= selected_year <= today.year:
        selected_year = today.year

    if view == "month":
        period_start = selected_month
        period_end = period_start + timedelta(days=monthrange(period_start.year, period_start.month)[1])
        period_label = period_start.strftime("%B %Y")
        chart_buckets = {
            period_start + timedelta(days=offset): 0.0
            for offset in range((period_end - period_start).days)
        }
    else:
        period_start = date(selected_year, 1, 1)
        period_end = date(selected_year + 1, 1, 1)
        period_label = str(selected_year)
        chart_buckets = {date(selected_year, month, 1): 0.0 for month in range(1, 13)}
    bucket_counts = {bucket: 0 for bucket in chart_buckets}

    start_at = datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc)
    end_at = datetime.combine(period_end, datetime.min.time(), tzinfo=timezone.utc)
    period_bills = data_manager.get_bills_between(start_at, end_at)
    total_value = 0.0
    party_totals = {}
    enriched_bills = []

    for bill_record in period_bills:
        bill = bill_record.get("bill") or {}
        amount = float(bill_record.get("total_value") or 0)
        party_name = bill.get("party_name") or "Unknown party"
        total_value += amount
        party_total = party_totals.setdefault(party_name, {"amount": 0.0, "bill_count": 0})
        party_total["amount"] += amount
        party_total["bill_count"] += 1

        created_at = bill_record.get("created_at")
        try:
            created_datetime = created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            created_date = created_datetime.astimezone(timezone.utc).date() if created_datetime.tzinfo else created_datetime.date()
        except (TypeError, ValueError):
            created_date = None
        if view == "month":
            bucket = created_date
        else:
            bucket = date(selected_year, created_date.month, 1) if created_date and created_date.year == selected_year else None
        if bucket in chart_buckets:
            chart_buckets[bucket] += amount
            bucket_counts[bucket] += 1

        enriched_bills.append({
            "invoice_no": bill_record.get("invoice_no", ""),
            "party_name": party_name,
            "total_value": amount,
            "created_at": created_date.strftime("%d %b %Y") if created_date else str(created_at or "-"),
        })

    chart_days = [
        {
            "label": bucket.strftime("%d") if view == "month" else bucket.strftime("%b"),
            "date": bucket.strftime("%d %b %Y") if view == "month" else bucket.strftime("%B %Y"),
            "value": amount,
            "bill_count": bucket_counts[bucket],
        }
        for bucket, amount in chart_buckets.items()
        if amount != 0
    ]
    chart_max = max((bucket["value"] for bucket in chart_days), default=0.0)
    party_summaries = sorted(
        ({"name": name, **values} for name, values in party_totals.items()),
        key=lambda party: party["amount"],
        reverse=True,
    )
    return render_template(
        "admin_analytics.html",
        bills=enriched_bills[:10],
        bill_count=len(period_bills),
        total_value=total_value,
        party_summaries=party_summaries,
        party_count=len(party_summaries),
        chart_days=chart_days,
        chart_max=chart_max,
        view=view,
        selected_month=selected_month.strftime("%Y-%m"),
        selected_year=selected_year,
        period_label=period_label,
    )

@app.route("/admin/approve/<type_>/<path:name>")
def admin_approve(type_, name):
    if not session.get("admin"):
        return jsonify({"error": "unauthorized"}), 401
    data_manager.approve_pending(type_, name)
    return jsonify({"status": "approved"})

@app.route("/admin/approve-bulk", methods=["POST"])
def admin_approve_bulk():
    if not session.get("admin"):
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    requests_to_approve = payload.get("requests")
    if not isinstance(requests_to_approve, list) or not requests_to_approve:
        return jsonify({"error": "Select at least one pending request"}), 400
    if len(requests_to_approve) > 1000:
        return jsonify({"error": "Select no more than 1000 requests at a time"}), 400

    approved = 0
    failed = []
    for pending_request in requests_to_approve:
        if not isinstance(pending_request, dict):
            failed.append({"error": "Invalid pending request"})
            continue
        type_ = pending_request.get("type")
        name = pending_request.get("name")
        if type_ not in {"party", "transport"} or not isinstance(name, str) or not name.strip():
            failed.append({"type": type_, "name": name, "error": "Invalid pending request"})
            continue
        if data_manager.approve_pending(type_, name):
            approved += 1
        else:
            failed.append({"type": type_, "name": name, "error": "Request not found"})

    return jsonify({"approved": approved, "failed": failed})

@app.route("/admin/reject/<type_>/<path:name>")
def admin_reject(type_, name):
    if not session.get("admin"):
        return redirect("/admin/login")
    data_manager.reject_pending(type_, name)
    return jsonify({"status": "rejected"})  # ✅ respond with JSON instead of redirect

# --------------------------
# ✅ ADMIN PANEL MANAGEMENT
# --------------------------
from flask import jsonify, request
from bson.objectid import ObjectId, InvalidId

def serialize(doc):
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    elif "id" in doc:
        doc["id"] = str(doc["id"])
    return doc

@app.route("/admin")
def admin_home():
    return render_template("admin.html")


@app.route("/admin/data")
def admin_data():
    table = request.args.get("table")

    if table not in ["parties", "transports", "cities", "pending_requests", "bank_details"]:
        return jsonify({"error": "Invalid table"}), 400

    docs = list(get_collection(table).find({}))
    docs = [serialize(d) for d in docs]  # convert _id → id

    return jsonify(docs)




@app.route("/admin/add", methods=["POST"])
def admin_add():
    data = request.json
    table = data.get("table")
    if table == "parties":
        document = {"name": normalize_text(data["name"]), "gstin": normalize_gstin(data["gstin"]), "place": normalize_text(data["place"]), "pincode": normalize_pincode(data.get("pincode", "")), "fixed_place": bool(data.get("fixed_place", 0))}
    elif table == "transports":
        document = {"name": normalize_text(data["name"]), "gstin": normalize_gstin(data["gstin"])}
    elif table == "cities":
        document = {"city": normalize_text(data["city"]), "state": normalize_text(data["state"]), "pincode": normalize_pincode(data.get("pincode", ""))}
    elif table == "pending_requests":
        document = {"type": data["type"], "name": normalize_text(data["name"]), "gstin": normalize_gstin(data["gstin"]), "place": normalize_text(data.get("place", "")), "pincode": normalize_pincode(data.get("pincode", ""))}
    elif table == "bank_details":
        document = {"bank_name": data["bank_name"], "account_number": data["account_number"], "ifsc": data["ifsc"]}
    else:
        return jsonify({"error": "Invalid table"}), 400

    result = get_collection(table).insert_one(document)
    return jsonify({"status": "ok"})



@app.route("/admin/delete", methods=["POST"])
def admin_delete():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    table = data.get("table")
    record_id = data.get("id")

    # ✅ Allowed tables
    ALLOWED_TABLES = ["parties", "transports", "cities", "pending_requests", "bank_details"]
    if table not in ALLOWED_TABLES:
        return jsonify({"error": "Invalid table"}), 400

    # ✅ Validate record_id
    if DB_BACKEND == "mongodb":
        try:
            record_id = ObjectId(record_id)
        except (InvalidId, TypeError):
            return jsonify({"error": "Invalid record id"}), 400

    # ✅ Delete record
    result = get_collection(table).delete_one({"_id" if DB_BACKEND == "mongodb" else "id": record_id})

    if result.deleted_count == 0:
        return jsonify({"error": "Record not found"}), 404

    return jsonify({"status": "deleted"})


def format_gstin(gstin: str) -> str:
    """Format GSTIN by inserting spaces every 4 characters for readability."""
    gstin = gstin.replace(" ", "").upper()  # Remove existing spaces and normalize case
    print(identify_number_type(gstin))
    if identify_number_type(gstin) == "GST" and identify_number_type(gstin) != "INVALID":
        return gstin  # Return as is if not a valid GSTIN
    else:
        return f"URP-{gstin}"
    

def identify_number_type(number: str) -> str:
    """
    Identify whether the input is a GST number, PAN number, or Aadhaar number.
    Returns one of: 'GST', 'PAN', 'AADHAAR', or 'INVALID'
    """

    number = number.strip().upper()  # Normalize input
    
    # GSTIN format: 15 characters -> 2 digits, 10 chars (PAN), 1 char, Z, 1 checksum
    gst_pattern = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$')
    
    # PAN format: 10 characters -> 5 letters, 4 digits, 1 letter
    pan_pattern = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')
    
    # Aadhaar format: 12 digits (may contain spaces)
    aadhaar_pattern = re.compile(r'^[0-9]{12}$')
    
    if gst_pattern.match(number):
        return "GST"
    elif pan_pattern.match(number):
        return "PAN"
    elif aadhaar_pattern.match(number):
        return "AADHAAR"
    else:
        return "INVALID"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5091))
    app.run(host="0.0.0.0", port=port, debug=True)
