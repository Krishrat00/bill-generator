from flask import Flask, render_template, request, send_file
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from PIL import Image
import fitz  # PyMuPDF

app = Flask(__name__)

def create_pdf(data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Outer border
    c.rect(10*mm, 10*mm, width-20*mm, height-20*mm)

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, height-20*mm, "ANANT CREATION")

    c.setFont("Helvetica", 10)
    c.drawString(20*mm, height-30*mm, f"Name: {data.get('customer_name', '')}")
    c.drawRightString(width-20*mm, height-30*mm, f"Date: {data.get('date', '')}")

    # Table column lines
    table_top = height-50*mm
    table_bottom = 40*mm
    col_x = [20*mm, 90*mm, 120*mm, 150*mm, width-20*mm]

    # vertical lines
    for x in col_x:
        c.line(x, table_bottom, x, table_top)

    # horizontal lines (10 rows)
    row_height = (table_top - table_bottom) / 10
    for i in range(11):
        y = table_bottom + i*row_height
        c.line(20*mm, y, width-20*mm, y)

    # headers
    c.setFont("Helvetica-Bold", 9)
    headers = ["Description", "Quantity", "Rate", "Amount"]
    for i, h in enumerate(headers):
        c.drawCentredString((col_x[i]+col_x[i+1])/2, table_top+5, h)

    # fill rows with data
    c.setFont("Helvetica", 9)
    products = data.get("products", [])
    for i, p in enumerate(products[:10]):
        y = table_top - (i+0.7)*row_height
        c.drawString(col_x[0]+2*mm, y, p.get("desc", ""))
        c.drawCentredString((col_x[1]+col_x[2])/2, y, p.get("qty", ""))
        c.drawCentredString((col_x[2]+col_x[3])/2, y, p.get("rate", ""))
        c.drawCentredString((col_x[3]+col_x[4])/2, y, p.get("amount", ""))

    # total
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(col_x[-1]-2*mm, table_bottom-10, f"TOTAL: {data.get('total', '')}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

@app.route('/')
def form():
    return render_template('form.html')

@app.route('/preview', methods=['POST'])
def preview():
    data = request.form.to_dict(flat=True)
    products = []
    for i in range(1, 11):
        desc = request.form.get(f'desc{i}', '')
        qty = request.form.get(f'qty{i}', '')
        rate = request.form.get(f'rate{i}', '')
        amount = request.form.get(f'amount{i}', '')
        if desc or qty or rate or amount:
            products.append({"desc": desc, "qty": qty, "rate": rate, "amount": amount})
    data["products"] = products
    buffer = create_pdf(data)

    # convert pdf to image using PyMuPDF
    doc = fitz.open(stream=buffer.getvalue(), filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap()
    img_bytes = pix.tobytes("png")

    return send_file(
        io.BytesIO(img_bytes),
        mimetype='image/png',
        as_attachment=False,
        download_name='preview.png'
    )

@app.route('/download', methods=['POST'])
def download():
    data = request.form.to_dict(flat=True)
    products = []
    for i in range(1, 11):
        desc = request.form.get(f'desc{i}', '')
        qty = request.form.get(f'qty{i}', '')
        rate = request.form.get(f'rate{i}', '')
        amount = request.form.get(f'amount{i}', '')
        if desc or qty or rate or amount:
            products.append({"desc": desc, "qty": qty, "rate": rate, "amount": amount})
    data["products"] = products
    buffer = create_pdf(data)
    return send_file(buffer, as_attachment=True, download_name="bill.pdf", mimetype="application/pdf")

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
