from flask import Flask, render_template, request, send_file
from bill_template import create_photo_style_bill
import io, fitz  # PyMuPDF

app = Flask(__name__)
last_pdf_data = None  # stores last generated PDF bytes for download

@app.route('/')
def index():
    return render_template('form.html')

@app.route('/preview', methods=['POST'])
def preview_bill():
    global last_pdf_data
    # Collect items
    item_names = request.form.getlist('item_name')
    qtys = request.form.getlist('qty')
    mtrs = request.form.getlist('mtr')
    rates = request.form.getlist('rate')
    amts = request.form.getlist('amount')

    items = []
    for i in range(len(item_names)):
        if item_names[i].strip():
            items.append({
                "name": item_names[i],
                "qty": qtys[i],
                "mtr": mtrs[i],
                "rate": rates[i],
                "amount": amts[i],
            })

    data = {
        "bill_no": request.form.get('bill_no',''),
        "date": request.form.get('date',''),
        "ch_no": request.form.get('ch_no',''),
        "customer_name": request.form.get('customer_name',''),
        "gstin": request.form.get('gstin',''),
        "items": items,
        "pcs_total": request.form.get('pcs_total',''),
        "gst_amount": request.form.get('gst_amount',''),
        "grand_total": request.form.get('grand_total','')
    }

    # Build PDF in memory
    pdf_buffer = create_photo_style_bill(data)
    last_pdf_data = pdf_buffer.getvalue()

    # Render first page to PNG using PyMuPDF (no external poppler needed)
    doc = fitz.open(stream=last_pdf_data, filetype="pdf")
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")

    return send_file(io.BytesIO(img_bytes), mimetype='image/png')

@app.route('/download', methods=['GET'])
def download_bill():
    global last_pdf_data
    if not last_pdf_data:
        return "No bill generated yet", 400
    return send_file(io.BytesIO(last_pdf_data), download_name="Bill.pdf", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
