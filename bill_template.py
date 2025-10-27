from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.units import mm
from num2words import num2words  # pip install num2words


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
    c.drawString(35, height - 74, "1048-49, Shree Mahalaxmi Market, Ring Road, Surat-395007")
    c.drawString(35, height - 88, "GSTIN: 24AHJPR6707K1ZY    MO: 9377178174")

    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(width - 35, height - 60, f"Invoice No: {data['invoice_no']}")
    c.drawRightString(width - 35, height - 74, f"Date: {data['date']}")

    # Line under header
    c.line(30, height - 95, width - 30, height - 95)

    # ===== PARTY DETAILS =====
    y = height - 110
    c.setFont("Helvetica-Bold", 9)
    c.drawString(35, y, "Party's Name:")
    c.setFont("Helvetica", 9)
    c.drawString(110, y, data["party_name"])

    c.setFont("Helvetica-Bold", 9)
    c.drawString(300, y, "Transport:")
    c.setFont("Helvetica", 9)
    c.drawString(365, y, data["transport"])

    y -= 12
    c.setFont("Helvetica-Bold", 9)
    c.drawString(35, y, "Place:")
    c.setFont("Helvetica", 9)
    c.drawString(110, y, data["place"])

    y -= 12
    c.setFont("Helvetica-Bold", 9)
    c.drawString(35, y, "GSTIN No:")
    c.setFont("Helvetica", 9)
    c.drawString(110, y, data["party_gstin"])

    # Draw line under party details
    c.line(30, y - 5, width - 30, y - 5)

    # ===== ITEM TABLE =====
    table_data = [["Item", "HSN/SAC", "Qty", "Rate", "Amount"]]
    total = 0
    for item in data["items"]:
        amount = item["qty"] * item["rate"]
        total += amount
        table_data.append([
            item["name"], "5407", f"{item['qty']:.2f}", f"{item['rate']:.2f}", f"{amount:.2f}"
        ])

    # Pad to 15 item rows (excluding header)
    while len(table_data) < 16:
        table_data.append(["", "", "", "", ""])

    gst = total * 0.05
    grand_total = total + gst

    # Add totals as last 3 rows in the table
    table_data.append(["", "", "", "Total", f"{total:.2f}"])
    table_data.append(["", "", "", "Add IGST @5%", f"{gst:.2f}"])
    table_data.append(["", "", "", "Grand Total", f"{grand_total:.2f}"])

    table = Table(table_data, colWidths=[160, 80, 70, 90, 100])
    n = len(table_data)
    style = TableStyle([
        # Header row: full grid
        ('GRID', (0, 0), (-1, 0), 0.6, colors.black),
        # Left and right border for all rows
        ('LINEBEFORE', (0, 0), (0, n-1), 0.6, colors.black),
        ('LINEAFTER', (-1, 0), (-1, n-1), 0.6, colors.black),
        # Vertical lines for all rows (column separators)
        ('LINEBEFORE', (1, 0), (1, n-1), 0.6, colors.black),
        ('LINEBEFORE', (2, 0), (2, n-1), 0.6, colors.black),
        ('LINEBEFORE', (3, 0), (3, n-1), 0.6, colors.black),
        ('LINEBEFORE', (4, 0), (4, n-1), 0.6, colors.black),
        # No horizontal lines for body rows except totals
        ('LINEABOVE', (0, n-3), (-1, n-3), 0.6, colors.black),  # line above totals
        # Header formatting
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        # Alignment
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        # Make Total, Add IGST @5%, Grand Total keys and values bold
        ('FONTNAME', (3, n-3), (4, n-1), 'Helvetica-Bold'),
        # Set all other body cells to Helvetica (excluding header and last 3 rows)
        ('FONTNAME', (0, 1), (2, n-4), 'Helvetica'),
        ('FONTNAME', (3, 1), (3, n-4), 'Helvetica'),
        ('FONTNAME', (4, 1), (4, n-4), 'Helvetica'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, n-1), (-1, n-1), 0.6, colors.black),


    ])
    table.setStyle(style)

    # Correct table placement (just below party details)
    table_x = 30
    # Place table just below party details (y - 20 for spacing)
    table_y = y - 20
    table.wrapOn(c, width, height)
    _, table_height = table.wrap(0, 0)
    table.drawOn(c, table_x, table_y - table_height)

    grand_total_words = num2words(round(grand_total), lang='en_IN')  # Indian numbering system
    grand_total_words = grand_total_words.replace(',', '').title() + " Rupees Only"

    # Create small table for amount in words
    words_table_data = [
        ["Grand Total (in Words)", grand_total_words]
    ]

    words_table = Table(words_table_data, colWidths=[160, 340])
    words_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    # Place the words table just below the main table
    words_table.wrapOn(c, width, height)
    _, words_table_height = words_table.wrap(0, 0)
    words_table.drawOn(c, table_x, table_y - table_height - words_table_height - 5)

    # ===== FOOTER =====
    c.setFont("Helvetica-Bold", 9)
    c.drawString(35, 55, "For ANANT CREATION")
    c.setFont("Helvetica", 9)
    c.drawString(35, 40, "Authorised Signatory")

    c.save()
    print(f"✅ Invoice generated successfully: {filename}")

    return total