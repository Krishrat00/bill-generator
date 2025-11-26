import re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.units import mm
from num2words import num2words  # pip install num2words
from db import get_collection

def sanitize_string(s):
    """
    Removes unwanted special characters and normalizes whitespace.
    Allows letters, numbers, spaces, and .,-/
    """
    if not s:
        return ""
    # 1. Remove unwanted characters
    # (Allows word chars, whitespace, and .,-/)
    s = re.sub(r'[^a-zA-Z\s]', '', s)
    # 2. Normalize whitespace (replace multiple spaces/tabs/etc. with a single space)
    s = " ".join(s.split())
    return s

def get_bank_details():
    col = get_collection("bank_details")  # ← pass the name here
    return list(col.find({}, {"_id": 0}))

def generate_invoice(data, filename="invoice_fixed.pdf"):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # ===== OUTER BORDER =====
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.rect(20, 20, width - 40, height - 40)

    # ===== HEADER =====
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 35, "TAX INVOICE")

    c.setFont("Helvetica-Bold", 10)
    c.drawString(35, height - 60, "ANANT CREATION")
    c.setFont("Helvetica", 9)
    c.drawString(35, height - 74, "1048-49, Shree Mahalaxmi Market, Ring Road, Surat-395002")
    c.drawString(35, height - 88, "GSTIN: 24AHJPR6707K1ZY    MO: 9377178174")

    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(width - 35, height - 60, f"Invoice No: {data['invoice_no']}")
    c.drawRightString(width - 35, height - 74, f"Date: {data['date']}")

    # Line under header
    c.line(30, height - 95, width - 30, height - 95)

    # ===== PARTY DETAILS (✅ Party Name Capitalized) =====
    y = height - 110

    # Get and sanitize the data
    # ✅ Capitalized Party Name
    party_name = sanitize_string(data.get("party_name", "")).upper() 
    transport = sanitize_string(data.get("transport", "")).upper()
    place = data.get("place", "").upper()
    party_gstin = data.get("party_gstin", "")
    transport_gstin = data.get("transport_gstin", "") 

    # --- Row 1 ---
    c.setFont("Helvetica-Bold", 9)
    c.drawString(35, y, "Party's Name:")
    c.setFont("Helvetica", 9)
    c.drawString(110, y, party_name) # <- sanitized and capitalized

    c.setFont("Helvetica-Bold", 9)
    c.drawString(300, y, "Transport:")
    c.setFont("Helvetica", 9)
    c.drawString(365, y, transport) # <- sanitized

    # --- Row 2 ---
    y -= 12
    c.setFont("Helvetica-Bold", 9)
    c.drawString(35, y, "Place:")
    c.setFont("Helvetica", 9)
    c.drawString(110, y, place) # <- sanitized

    c.setFont("Helvetica-Bold", 9)
    c.drawString(300, y, "Transport GSTIN:")
    c.setFont("Helvetica", 9)
    c.drawString(385, y, transport_gstin) 

    # --- Row 3 ---
    y -= 12
    c.setFont("Helvetica-Bold", 9)
    c.drawString(35, y, "GSTIN No:")
    c.setFont("Helvetica", 9)
    c.drawString(110, y, party_gstin)

    # Draw line under party details
    c.line(30, y - 5, width - 30, y - 5)

    # ===== ITEM TABLE =====
    table_data = [["Item", "HSN/SAC", "Qty", "Unit", "Rate", "Amount"]]
    total = 0
    for item in data["items"]:
        amount = item["qty"] * item["rate"]
        total += amount
        table_data.append([
            item["name"],
            "5407",
            f"{item['qty']:.2f}",
            item["unit"],
            f"{item['rate']:.2f}",
            f"{amount:.2f}"
        ])

    # Pad to 15 item rows (excluding header)
    while len(table_data) < 16:
        table_data.append(["", "", "", "", "", ""])

    rounded_total = round(total)

    gst = rounded_total * 0.05
    grand_total = rounded_total + gst

    # Add totals as last 3 rows in the table
    table_data.append(["", "", "", "", "Total", f"{rounded_total:.2f}"])
    table_data.append(["", "", "", "", "Add IGST @5%", f"{gst:.2f}"])
    table_data.append(["", "", "", "", "Grand Total", f"{grand_total:.2f}"])

    col_widths = [150, 70, 60, 60, 80, 85] 
    table = Table(table_data, colWidths=col_widths)

    n = len(table_data)
    style = TableStyle([
        ('GRID', (0, 0), (-1, 0), 0.6, colors.black),
        ('BOX', (0, 0), (-1, n - 1), 0.6, colors.black),
        ('LINEBEFORE', (1, 0), (1, n - 1), 0.6, colors.black),
        ('LINEBEFORE', (2, 0), (2, n - 1), 0.6, colors.black),
        ('LINEBEFORE', (3, 0), (3, n - 1), 0.6, colors.black),
        ('LINEBEFORE', (4, 0), (4, n - 1), 0.6, colors.black),
        ('LINEBEFORE', (5, 0), (5, n - 1), 0.6, colors.black),
        ('LINEABOVE', (0, n - 3), (-1, n - 3), 0.6, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (4, n - 3), (5, n - 1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, n - 1), (-1, n - 1), 0.6, colors.black),
    ])
    table.setStyle(style)

    table_x = 30
    table_y = y - 20 
    table.wrapOn(c, width, height)
    _, table_height = table.wrap(0, 0)
    table.drawOn(c, table_x, table_y - table_height)

    # ===== GRAND TOTAL IN WORDS =====
    grand_total_words = num2words(round(grand_total), lang='en_IN').replace(',', '').title() + " Rupees Only"
    words_table_data = [["Grand Total (in Words)", grand_total_words]]
    words_table = Table(words_table_data, colWidths=[150, 355])
    words_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, colors.black),
        ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    words_table.wrapOn(c, width, height)
    _, words_table_height = words_table.wrap(0, 0)
    words_table.drawOn(c, table_x, table_y - table_height - words_table_height - 5)
    
    # ===== TERMS & CONDITIONS =====
    terms = [
        "1. Goods once sold will not be taken back.",
        "2. Any complaint should be made within 7 days of receipt of goods.",
        "3. Interest @24% p.a. will be charged if payment is not made within due date.",
        "4. Subject to Surat Jurisdiction only.",
        "5. Please issue A/c Payee Cheque only."
    ]
    section_y = table_y - table_height - words_table_height - 40
    c.setFont("Helvetica-Bold", 9)
    c.drawString(35, section_y, "Terms & Conditions:")
    c.setFont("Helvetica", 9)
    y_offset = section_y - 12
    for t in terms:
        c.drawString(45, y_offset, t)
        y_offset -= 10

    bank_section_y = y_offset - 20

    # ===== BANK DETAILS =====
    banks = get_bank_details()
    if banks:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(35, bank_section_y, "Bank Details:")
        bank_data = [["Bank Name", "Account No.", "IFSC"]]
        for bank in banks:
            bank_data.append([
                bank["bank_name"],
                bank["account_number"],
                bank["ifsc"]
            ])
        bank_table = Table(bank_data, colWidths=[180, 150, 150])
        bank_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        bank_table.wrapOn(c, width, height)
        _, bank_table_height = bank_table.wrap(0, 0)
        bank_table.drawOn(c, 35, bank_section_y - 15 - bank_table_height)
        sig_y = bank_section_y - bank_table_height - 40
    else:
        sig_y = y_offset - 40
    sig_y -= 40

    # ===== SIGNATURE SECTION =====
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(550, sig_y, "For ANANT CREATION")
    c.setFont("Helvetica", 9)
    c.drawRightString(550, sig_y - 15, "Authorised Signatory")

    c.save()
    print(f"✅ Invoice generated successfully: {filename}")

    return total
