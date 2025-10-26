from flask import Flask, render_template, request, jsonify, send_file, session, redirect
import io, os
from datetime import datetime
from bill_template import generate_invoice
from data_manager import DataManager

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecret")
data_manager = DataManager()

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
    party = data_manager.get_party(name)  # correct method
    if not party:
        return jsonify({"gstin": "", "place": "", "fixed_place": False})
    return jsonify({
        "gstin": party.get("gstin",""),
        "place": party.get("place",""),
        "fixed_place": party.get("fixed_place", False)  # ✅ return stored value
    })

@app.route("/get_transport_details")
def get_transport_details():
    name = request.args.get("name")
    transport = data_manager.get_transport(name)  # ✅ correct method
    if not transport:
        return jsonify({"gstin": ""})
    return jsonify({"gstin": transport.get("gstin","")})


@app.route("/save_city")
def save_city():
    city = request.args.get("city", "")
    state = request.args.get("state", "")
    data_manager.add_city(city, state)
    return jsonify({"status": "ok"})

# ---------- Add Pending ----------
@app.route("/add_pending", methods=["POST"])
def add_pending():
    data = request.get_json()
    data_manager.add_pending(
        type_=data["type"],
        name=data["name"],
        gstin=data.get("gstin",""),
        place=data.get("place","")
    )
    return jsonify({"status":"ok"})

# ---------- Download Bill ----------
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
        "party_name": form.get("customer_name", ""),
        "place": form.get("ch_no", ""),
        "party_gstin": form.get("gstin", ""),
        "transport": form.get("transport", ""),
        "items": []
    }

    for name, qty, rate in zip(form.getlist("item_name[]"), form.getlist("qty[]"), form.getlist("rate[]")):
        if name and qty and rate:
            data["items"].append({"name": name, "qty": float(qty), "rate": float(rate)})

    output = io.BytesIO()
    generate_invoice(data, output)
    output.seek(0)
    filename = f"{data['invoice_no']}_ANANT_CREATION.pdf"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/pdf")

# ---------- Admin Login ----------
@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        user = request.form.get("username","")
        pwd = request.form.get("password","")
        if user==ADMIN_USER and pwd==ADMIN_PASS:
            session["admin"] = True
            return redirect("/admin/pending")
        else:
            return "Invalid credentials", 403
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin/login")

# ---------- Admin Pending ----------
@app.route("/admin/pending")
def admin_pending():
    if not session.get("admin"): return redirect("/admin/login")
    pending = data_manager.get_all_pending()
    return render_template("admin_tab.html", pending=pending)

@app.route("/admin/approve/<key>")
def admin_approve(key):
    if not session.get("admin"): return redirect("/admin/login")
    data_manager.approve_pending(key)
    return redirect("/admin/pending")

@app.route("/admin/reject/<key>")
def admin_reject(key):
    if not session.get("admin"): return redirect("/admin/login")
    data_manager.reject_pending(key)
    return redirect("/admin/pending")


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5091))
    app.run(host="0.0.0.0", port=port, debug=True)
