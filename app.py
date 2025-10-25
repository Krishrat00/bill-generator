
from flask import Flask, render_template, request, send_file
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from PIL import Image
from pdf2image import convert_from_bytes
from bill_template import generate_invoice

app = Flask(__name__)

@app.route('/download', methods=['POST'])
def download():
    form = request.form.to_dict(flat=True)
    # Map form fields to expected keys for generate_invoice
    # data = {
    #     "invoice_no": form.get("bill_no", ""),
    #     "date": form.get("date", ""),
    #     "party_name": form.get("customer_name", ""),
    #     "place": form.get("ch_no", ""),
    #     "party_gstin": form.get("gstin", ""),
    #     "transport": form.get("transport", ""),
    #     "items": []
    # }

    data = {
    "invoice_no": "53X2",
    "date": "09/06/2025",
    "party_name": "JAVED AHMAD",
    "place": "MAUNATH BHANJAN U.P.",
    "party_gstin": "09APDPA6944B1Z8",
    "transport": "CALCUTTA EXPRESS",
    "items": [
        {"name": "LINEN", "qty": 40.5, "rate": 552.5},
        {"name": "SHRIMAN", "qty": 39.5, "rate": 473.25},
        # {"name": "KING KOT", "qty": 8.5, "rate": 465.35}
    ]
}
    # Collect items from form (assuming multiple items can be submitted)
    # If you use JS to add more items, you should use name="item_name[]", etc. for arrays
    # For now, handle a single item as per your form.html
    item = {
        "name": form.get("item_name", ""),
        "qty": float(form.get("qty", 0) or 0),
        "rate": float(form.get("rate", 0) or 0)
    }
    if item["name"] or item["qty"] or item["rate"]:
        data["items"].append(item)
    # Generate the invoice PDF in memory
    output = io.BytesIO()
    generate_invoice(data, output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="bill.pdf", mimetype="application/pdf")



@app.route('/')
def form():
    return render_template('form.html')

# Add this at the end to run the app
if __name__ == '__main__':
    app.run(debug=True)

# @app.route('/preview', methods=['POST'])
# def preview():
#     data = request.form.to_dict(flat=True)
#     products = []
#     for i in range(1, 11):
#         desc = request.form.get(f'desc{i}', '')
#         qty = request.form.get(f'qty{i}', '')
#         rate = request.form.get(f'rate{i}', '')
#         amount = request.form.get(f'amount{i}', '')
#         if desc or qty or rate or amount:
#             products.append({"desc": desc, "qty": qty, "rate": rate, "amount": amount})
#     data["products"] = products
#     buffer = create_pdf(data)
#
#     # convert pdf to image using pdf2image
#     images = convert_from_bytes(buffer.getvalue())
#     img_buffer = io.BytesIO()
#     images[0].save(img_buffer, format='PNG')
#     img_buffer.seek(0)
#
#     return send_file(
#         img_buffer,
#         mimetype='image/png',
#         as_attachment=False,
#         download_name='preview.png'
#     )

