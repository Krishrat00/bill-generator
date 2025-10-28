from flask import Flask, render_template, request, jsonify, send_file, session, redirect
import io, os
from datetime import datetime
from bill_template import generate_invoice
from data_manager import DatabaseManager

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecret")
data_manager = DatabaseManager()

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "password")

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
        return jsonify({"gstin": "", "pan": "", "aadhar": "", "place": "", "fixed_place": False})
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
    city = request.args.get("city", "")
    state = request.args.get("state", "")
    data_manager.add_city(city, state)
    return jsonify({"status": "ok"})

@app.route("/add_pending", methods=["POST"])
def add_pending():
    data = request.get_json()
    data_manager.add_pending(
        type_=data["type"],
        name=data["name"],
        gstin=data.get("gstin", ""),
        place=data.get("place", "")
    )
    return jsonify({"status": "ok"})

@app.route("/message")
def message_page():
    return render_template("message.html")

@app.route("/download", methods=["POST"])
def download():
    form = request.form

    # Required fields except GSTIN (handled separately)
    required_fields = ["bill_no", "date", "customer_name", "ch_no", "transport"]
    for field in required_fields:
        if not form.get(field):
            return f"{field} is required", 400

    # Validate ID fields (at least one of GSTIN, PAN, or Aadhaar must exist)
    if not any([form.get("gstin"), form.get("pan"), form.get("aadhar")]):
        return "At least one of GSTIN, PAN, or Aadhaar is required", 400

    try:
        formatted_date = datetime.strptime(form.get("date", ""), "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        formatted_date = form.get("date", "")

    data = {
        "invoice_no": form.get("bill_no", ""),
        "date": formatted_date,
        "party_name": form.get("customer_name", ""),
        "place": form.get("ch_no", ""),
        "party_gstin": form.get("gstin", ""),
        "party_pan": form.get("pan", ""),
        "party_aadhar": form.get("aadhar", ""),
        "transport": form.get("transport", ""),
        "units": form.getlist('unit[]'),
        "items": []
    }

    # 🧠 Auto-derive GSTIN for URP case

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

    existing_party = data_manager.get_party(data["party_name"])
    if not existing_party:
        data_manager.add_pending(
            type_="party",
            name=data["party_name"],
            gstin=data.get("party_gstin", ""),
            pan=data.get("party_pan", ""),
            aadhar=data.get("party_aadhar", ""),
            place=data.get("place", "")
        )
    if not data["party_gstin"]:
        if data["party_pan"]:
            data["party_gstin"] = f"URP - {data['party_pan']}"
        elif data["party_aadhar"]:
            data["party_gstin"] = f"URP - {data['party_aadhar']}"
            
    output = io.BytesIO()
    total = generate_invoice(data, output)

    session['invoice_data'] = {
        "invoice_no": data["invoice_no"],
        "date": data["date"],
        "party_gstin": data["party_gstin"],
        "place": data["place"],
        "total_value": total,
    }

    # Save to pending requests automatically if new party
    
    output.seek(0)
    filename = f"{data['invoice_no']}_ANANT_CREATION.pdf"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/pdf")

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

@app.route("/admin/approve/<type_>/<name>")
def admin_approve(type_, name):
    if not session.get("admin"):
        return redirect("/admin/login")
    data_manager.approve_pending(type_, name)
    return redirect("/admin/pending")

@app.route("/admin/reject/<type_>/<name>")
def admin_reject(type_, name):
    if not session.get("admin"):
        return redirect("/admin/login")
    data_manager.reject_pending(type_, name)
    return redirect("/admin/pending")

# --------------------------
# ✅ ADMIN PANEL MANAGEMENT
# --------------------------
from flask import jsonify, request
from db import get_db
conn = get_db()
@app.route("/admin")
def admin_home():
    return render_template("admin.html")


@app.route("/admin/data")
def admin_data():
    table = request.args.get("table")
    allowed = ["parties", "transports", "cities", "pending_requests","bank_details"]
    if table not in allowed:
        return jsonify({"error": "Invalid table"}), 400
    
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/admin/add", methods=["POST"])
def admin_add():
    data = request.json
    table = data.get("table")

    if table == "parties":
        conn.execute("INSERT INTO parties (name, gstin, place, fixed_place) VALUES (?, ?, ?, ?)",
                        (data["name"], data["gstin"], data["place"], data.get("fixed_place", 0)))
    elif table == "transports":
        conn.execute("INSERT INTO transports (name, gstin) VALUES (?, ?)",
                        (data["name"], data["gstin"]))
    elif table == "cities":
        conn.execute("INSERT INTO cities (city, state) VALUES (?, ?)",
                        (data["city"], data["state"]))
    elif table == "pending_requests":
        conn.execute("INSERT INTO pending_requests (type, name, gstin, place) VALUES (?, ?, ?, ?)",
                        (data["type"], data["name"], data["gstin"], data.get("place", "")))
    elif table == "bank_details":
        conn.execute("INSERT INTO bank_details (bank_name, account_number, ifsc) VALUES (?, ?, ?)",
                        (data["bank_name"], data["account_number"], data["ifsc"]))
    else:
        return jsonify({"error": "Invalid table"}), 400

    conn.commit()
    return jsonify({"status": "ok"})


@app.route("/admin/delete", methods=["POST"])
def admin_delete():
    data = request.json
    table = data.get("table")
    record_id = data.get("id")

    allowed = ["parties", "transports", "cities", "pending_requests"]
    if table not in allowed:
        return jsonify({"error": "Invalid table"}), 400
    
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
    conn.commit()
    return jsonify({"status": "deleted"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5091))
    app.run(host="0.0.0.0", port=port, debug=True)
