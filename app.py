from flask import Flask, render_template, request, send_file
import io
from datetime import datetime
import os
from bill_template import generate_invoice

app = Flask(__name__)

@app.route('/')
def form():
    return render_template('form.html')

@app.route('/download', methods=['POST'])
def download():
    form = request.form

    # Format date as dd/mm/yyyy
    raw_date = form.get("date", "")
    try:
        formatted_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        formatted_date = raw_date

    # Prepare data for invoice
    data = {
        "invoice_no": form.get("bill_no", ""),
        "date": formatted_date,
        "party_name": form.get("customer_name", ""),
        "place": form.get("ch_no", ""),
        "party_gstin": form.get("gstin", ""),
        "transport": form.get("transport", ""),
        "items": []
    }

    # Collect multiple items
    item_names = form.getlist("item_name[]")
    qtys = form.getlist("qty[]")
    rates = form.getlist("rate[]")

    for name, qty, rate in zip(item_names, qtys, rates):
        if name and qty and rate:
            data["items"].append({
                "name": name,
                "qty": float(qty),
                "rate": float(rate)
            })

    # Generate the invoice PDF in memory
    output = io.BytesIO()
    generate_invoice(data, output)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name="bill.pdf", mimetype="application/pdf")


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
