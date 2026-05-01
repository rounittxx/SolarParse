# Generates a realistic MSEDCL-style electricity bill PDF for testing
# the extractor when you don't have a real customer bill handy.
#
#   python samples/generate_sample_bill.py
#
# Two outputs:
#   samples/sample_msedcl_bill.pdf  -- clean digital PDF (text layer)
#   samples/sample_msedcl_noisy.pdf -- second one with different values
#                                       to test the no-hardcoding promise

import sys
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, KeepTogether,
)


def _style():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("Brand", fontName="Helvetica-Bold", fontSize=18,
                         textColor=colors.HexColor("#0B5394")))
    s.add(ParagraphStyle("Sub", fontName="Helvetica", fontSize=9,
                         textColor=colors.HexColor("#444444")))
    s.add(ParagraphStyle("H", fontName="Helvetica-Bold", fontSize=10,
                         textColor=colors.white, alignment=0))
    s.add(ParagraphStyle("Cell", fontName="Helvetica", fontSize=9,
                         textColor=colors.HexColor("#222")))
    s.add(ParagraphStyle("CellB", fontName="Helvetica-Bold", fontSize=9))
    s.add(ParagraphStyle("Small", fontName="Helvetica", fontSize=8,
                         textColor=colors.HexColor("#666")))
    return s


def _header(s):
    return [
        Paragraph("MSEDCL", s["Brand"]),
        Paragraph("Maharashtra State Electricity Distribution Co. Ltd.", s["Sub"]),
        Paragraph("(A Government of Maharashtra Undertaking) -- "
                  "Prakashgad, Bandra (E), Mumbai 400 051", s["Sub"]),
        Spacer(1, 6),
    ]


def _kv_table(rows, s):
    data = [[Paragraph(k, s["CellB"]), Paragraph(str(v), s["Cell"])] for k, v in rows]
    t = Table(data, colWidths=[55*mm, 100*mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F4F6F8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _consumption_table(units_now, units_prev, s):
    head = [Paragraph(t, s["H"]) for t in
            ["Reading Date", "Previous Reading", "Current Reading", "Units Consumed"]]
    body = [
        Paragraph(date.today().strftime("%d-%m-%Y"), s["Cell"]),
        Paragraph(f"{units_prev:,}", s["Cell"]),
        Paragraph(f"{units_prev + units_now:,}", s["Cell"]),
        Paragraph(f"{units_now:,}", s["CellB"]),
    ]
    t = Table([head, body], colWidths=[40*mm, 38*mm, 38*mm, 38*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5394")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#aaaaaa")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _charges_table(units, s):
    # rough MSEDCL slab maths -- not exact, but realistic enough
    energy = round(units * 8.10, 2)
    fuel   = round(units * 0.52, 2)
    fixed  = 90.00
    duty   = round(energy * 0.16, 2)
    total  = round(energy + fuel + fixed + duty, 2)

    rows = [
        [Paragraph("Component", s["H"]), Paragraph("Amount (Rs)", s["H"])],
        ["Energy Charges",        f"{energy:,.2f}"],
        ["Fuel Adjustment Charge", f"{fuel:,.2f}"],
        ["Fixed Charges",         f"{fixed:,.2f}"],
        ["Electricity Duty",      f"{duty:,.2f}"],
        [Paragraph("<b>Total Amount Payable</b>", s["CellB"]),
         Paragraph(f"<b>Rs {total:,.2f}</b>", s["CellB"])],
    ]
    t = Table(rows, colWidths=[100*mm, 55*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5394")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#aaaaaa")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FFF7DA")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t, total


def build_bill(out_path, *,
               consumer_name, consumer_number, meter_number,
               address, billing_month, units, prev_units,
               tariff, connected_load, sanctioned_load):
    s = _style()
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=18*mm, bottomMargin=18*mm)

    flow = []
    flow.extend(_header(s))

    flow.append(Paragraph("ELECTRICITY BILL CUM RECEIPT", s["CellB"]))
    flow.append(Spacer(1, 8))

    due = date.today() + timedelta(days=15)
    flow.append(_kv_table([
        ("Consumer Name",    consumer_name),
        ("Consumer Number",  consumer_number),
        ("Meter Number",     meter_number),
        ("Service Address",  address),
        ("Billing Period",   billing_month),
        ("Bill Date",        date.today().strftime("%d-%m-%Y")),
        ("Due Date",         due.strftime("%d-%m-%Y")),
        ("Tariff Category",  tariff),
        ("Connected Load",   f"{connected_load} kW"),
        ("Sanctioned Load",  f"{sanctioned_load} kW"),
    ], s))

    flow.append(Spacer(1, 12))
    flow.append(Paragraph("Consumption Details", s["CellB"]))
    flow.append(Spacer(1, 4))
    flow.append(_consumption_table(units, prev_units, s))

    flow.append(Spacer(1, 12))
    flow.append(Paragraph("Bill Summary", s["CellB"]))
    flow.append(Spacer(1, 4))
    charges, total = _charges_table(units, s)
    flow.append(charges)

    flow.append(Spacer(1, 14))
    flow.append(Paragraph(
        f"Pay <b>Rs {total:,.2f}</b> by {due.strftime('%d-%m-%Y')} to avoid "
        f"late payment surcharge. Sample bill generated for testing the "
        f"Energybae solar load extractor -- not a real invoice.",
        s["Small"]))

    doc.build(flow)
    print(f"wrote: {out_path}")


if __name__ == "__main__":
    here = Path(__file__).parent

    # Bill 1: a "typical" Pune residential customer
    build_bill(
        here / "sample_msedcl_bill.pdf",
        consumer_name="Anurag Singh",
        consumer_number="020012345678",
        meter_number="MTR-9988-7766-55",
        address="Flat 304, Sukhwani Chambers, Kamala Cross Rd, MIDC, Pimpri Colony, Pune 411018",
        billing_month="April 2025",
        units=421,
        prev_units=14820,
        tariff="LT-I Residential",
        connected_load=4.5,
        sanctioned_load=5.0,
    )

    # Bill 2: a heavier user, different layout values, to prove
    # nothing in the system is hardcoded to bill #1
    build_bill(
        here / "sample_msedcl_noisy.pdf",
        consumer_name="Sharma Trading Co.",
        consumer_number="020077665544",
        meter_number="MTR-1122-3344-AA",
        address="Shop 12, Mahatma Phule Mandai, Pune 411002",
        billing_month="March 2025",
        units=1287,
        prev_units=46210,
        tariff="LT-II Commercial",
        connected_load=12.0,
        sanctioned_load=15.0,
    )
