from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import io

# Photo-style bill with: outer border, details box, vertical-only product lines, 10 fixed rows
def create_photo_style_bill(data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Outer border
    c.setLineWidth(1)
    c.rect(10*mm, 10*mm, width - 20*mm, height - 20*mm)

    # Header (match look from your sample)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height - 25*mm, "ANANT CREATION")
    c.setFont("Helvetica", 9)
    c.drawCentredString(width/2, height - 31*mm, "GST NO: 24AHJPR6707PK1ZY")
    c.drawCentredString(width/2, height - 37*mm, "1048-49, Shree Mahalaxmi Market, Surat - 395002")

    # Bill details box (two rows)
    box_left = 12*mm
    box_right = width - 12*mm
    box_top = height - 44*mm
    box_h = 18*mm
    c.rect(box_left, box_top - box_h, box_right - box_left, box_h)  # outer
    # middle horizontal
    c.line(box_left, box_top - box_h/2, box_right, box_top - box_h/2)
    # top row vertical dividers (Date | Bill No | Ch. No)
    v1 = box_left + (box_right - box_left) * 0.33
    v2 = box_left + (box_right - box_left) * 0.66
    c.line(v1, box_top, v1, box_top - box_h/2)
    c.line(v2, box_top, v2, box_top - box_h/2)

    c.setFont("Helvetica", 9)
    c.drawString(box_left + 3, box_top - 6, f"DATE: {data.get('date','')}")
    c.drawString(v1 + 3, box_top - 6, f"BILL NO: {data.get('bill_no','')}")
    c.drawString(v2 + 3, box_top - 6, f"CH. NO: {data.get('ch_no','')}")

    c.drawString(box_left + 3, box_top - box_h/2 - 6, f"TO: {data.get('customer_name','')}")
    c.drawString(v2 + 3, box_top - box_h/2 - 6, f"GSTIN NO: {data.get('gstin','')}")

    # Product table (header with top & bottom lines; rows only have verticals)
    table_top = box_top - box_h - 4*mm
    row_h = 9.5*mm  # visual height per row
    rows = 10
    table_h = row_h * rows + 7  # include header height
    left = 12*mm
    right = width - 12*mm

    # Column x positions (SR, PARTICULARS, QTY, MTR, RATE, AMOUNT)
    col_x = [left, left + 13*mm, left + 85*mm, left + 110*mm, left + 135*mm, left + 170*mm, right]

    # Vertical column lines
    for x in col_x:
        c.line(x, table_top, x, table_top - (row_h*rows) - 7)

    # Header lines
    c.line(left, table_top, right, table_top)  # header top
    c.line(left, table_top - 7, right, table_top - 7)  # header bottom

    # Header text
    headers = ["SR.", "PARTICULARS", "QTY", "MTR", "RATE", "AMOUNT"]
    c.setFont("Helvetica-Bold", 9)
    for i, h in enumerate(headers):
        cx = (col_x[i] + col_x[i+1]) / 2.0
        c.drawCentredString(cx, table_top - 5, h)

    # Table rows (no horizontal lines)
    c.setFont("Helvetica", 9)
    y = table_top - 7
    for i in range(rows):
        y -= row_h
        if i < len(data.get('items', [])):
            it = data['items'][i]
            # SR
            c.drawCentredString((col_x[0]+col_x[1])/2, y + 3, str(i+1))
            # Particulars (left aligned)
            c.drawString(col_x[1] + 2, y + 3, str(it.get('name',''))[:40])
            # Qty / Mtr / Rate centered
            c.drawCentredString((col_x[2]+col_x[3])/2, y + 3, str(it.get('qty','')))
            c.drawCentredString((col_x[3]+col_x[4])/2, y + 3, str(it.get('mtr','')))
            c.drawCentredString((col_x[4]+col_x[5])/2, y + 3, str(it.get('rate','')))
            # Amount right aligned
            c.drawRightString(col_x[6] - 3, y + 3, str(it.get('amount','')))

    # Totals box (right side)
    totals_top = table_top - (row_h*rows) - 9*mm
    totals_h = 18*mm
    c.rect(left, totals_top - totals_h, right - left, totals_h)
    # right partition for labels/values
    split = right - 40*mm
    c.line(split, totals_top, split, totals_top - totals_h)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(split + 3, totals_top - 6, "PCS TOTAL")
    c.drawRightString(right - 3, totals_top - 6, str(data.get('pcs_total','')))
    c.drawString(split + 3, totals_top - 12, "GST AMOUNT")
    c.drawRightString(right - 3, totals_top - 12, str(data.get('gst_amount','')))
    c.drawString(split + 3, totals_top - 18, "TOTAL AMOUNT")
    c.drawRightString(right - 3, totals_top - 18, str(data.get('grand_total','')))

    # Footer box (bank & terms)
    foot_top = totals_top - totals_h - 5*mm
    foot_h = 22*mm
    c.rect(left, foot_top - foot_h, right - left, foot_h)
    c.setFont("Helvetica", 8)
    c.drawString(left + 3, foot_top - 6, "A/C: Bank of Baroda, IFSC: BARB0DUMSUR")
    c.drawString(left + 3, foot_top - 12, "A/C: Central Bank of India, IFSC: CBIN0284947")
    c.drawString(left + 3, foot_top - 18, "1) Goods once sold will not be taken back.")
    c.drawString(left + 3, foot_top - 24, "2) Subject to Surat Jurisdiction.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
