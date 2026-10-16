"""Render the Learner's Performance Report as a PDF that mirrors the school's
official report-card form (landscape A4, two bordered panels).

All coordinates below are measured in points from the TOP-LEFT corner of the
page (matching how the reference form was laid out) and converted to
ReportLab's bottom-left origin at draw time.
"""

import os
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas

PAGE_W, PAGE_H = 841.8, 595.2

_BOOKMAN_CANDIDATES = {
    'Bookman': [
        r'C:\Windows\Fonts\BOOKOS.TTF',
        '/usr/share/fonts/truetype/bookman/BOOKOS.TTF',
    ],
    'Bookman-Bold': [
        r'C:\Windows\Fonts\BOOKOSB.TTF',
        '/usr/share/fonts/truetype/bookman/BOOKOSB.TTF',
    ],
    'Bookman-Italic': [
        r'C:\Windows\Fonts\BOOKOSI.TTF',
        '/usr/share/fonts/truetype/bookman/BOOKOSI.TTF',
    ],
    'Bookman-BoldItalic': [
        r'C:\Windows\Fonts\BOOKOSBI.TTF',
        '/usr/share/fonts/truetype/bookman/BOOKOSBI.TTF',
    ],
}
_FALLBACKS = {
    'Bookman': 'Times-Roman',
    'Bookman-Bold': 'Times-Bold',
    'Bookman-Italic': 'Times-Italic',
    'Bookman-BoldItalic': 'Times-BoldItalic',
}


def _register_fonts():
    fonts = {}
    for name, candidates in _BOOKMAN_CANDIDATES.items():
        fonts[name] = _FALLBACKS[name]
        for path in candidates:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    fonts[name] = name
                    break
                except Exception:
                    continue
    return fonts


_FONTS = _register_fonts()
REG = _FONTS['Bookman']
BOLD = _FONTS['Bookman-Bold']
ITAL = _FONTS['Bookman-Italic']
BOLDITAL = _FONTS['Bookman-BoldItalic']

BASE = 7.1  # base font size used across the whole form
LOGO_DEPED = os.path.join(settings.BASE_DIR, 'static', 'images', 'deped-logo.png')
LOGO_SCHOOL = os.path.join(settings.BASE_DIR, 'static', 'images', 'psyu-logo.png')

LEFT_CENTER = 210.05   # center x of the left panel content area
RIGHT_CENTER = 598.05  # center x of the right panel content area

# Grades table geometry (left panel)
GT_X = [47.0, 170.7, 201.1, 229.0, 259.4, 289.8, 373.1]  # column boundaries
GT_TOP = 265.8
GT_HDR1 = 14.1   # 'TERM' band height
GT_HDR2 = 14.3   # T1/T2/T3 band height
GT_AVG_H = 17.2  # General Average row height
GT_BOTTOM = 453.4

# Attendance table geometry (right panel)
AT_X = [435.7, 484.55, 505.8, 527.1, 548.5, 569.75, 591.1, 612.4,
        633.7, 655.0, 676.3, 697.6, 718.9, 760.4]
AT_Y = [44.9, 53.7, 71.3, 88.9, 106.5]
AT_MONTHS = ['Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr']
AT_ROWS = [('No. of Class', 'Days'), ('No. of Days', 'Present'), ('No. of Days', 'Absent')]


def _y(y_top):
    return PAGE_H - y_top


def _text(c, x, y_top, s, font=REG, size=BASE):
    c.setFont(font, size)
    c.drawString(x, _y(y_top), s)


def _ctext(c, cx, y_top, s, font=REG, size=BASE):
    c.setFont(font, size)
    c.drawCentredString(cx, _y(y_top), s)


def _hline(c, x0, x1, y_top, width=0.6):
    c.setLineWidth(width)
    c.line(x0, _y(y_top), x1, _y(y_top))


def _vline(c, x, y0_top, y1_top, width=0.6):
    c.setLineWidth(width)
    c.line(x, _y(y0_top), x, _y(y1_top))


def _box(c, x0, y0_top, x1, y1_top, width=0.6):
    c.setLineWidth(width)
    c.rect(x0, _y(y1_top), x1 - x0, y1_top - y0_top, stroke=1, fill=0)


def _fmt(value):
    if value is None:
        return ''
    return str(int(Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP)))


def _draw_left_panel(c, ctx):
    _box(c, 33.9, 26.7, 386.2, 533.2, width=1.2)

    if os.path.exists(LOGO_DEPED):
        c.drawImage(LOGO_DEPED, 45.9, _y(105.5), width=61.1, height=61.1, mask='auto')
    if os.path.exists(LOGO_SCHOOL):
        c.drawImage(LOGO_SCHOOL, 307.5, _y(104.1), width=67.2, height=63.0, mask='auto')

    _ctext(c, LEFT_CENTER, 52.1, 'Republic of the Philippines')
    _ctext(c, LEFT_CENTER, 60.9, 'Department of Education')
    _ctext(c, LEFT_CENTER, 78.5, 'REGION IX, ZAMBOANGA PENINSULA')
    _ctext(c, LEFT_CENTER, 87.3, 'SCHOOLS DIVISION OF ZAMBOANGA DEL SUR', BOLD)
    _ctext(c, LEFT_CENTER, 96.1, 'DUMINGA I DISTRICT')
    _ctext(c, LEFT_CENTER, 104.9, 'Dumingag, Zamboanga del Sur')
    _ctext(c, LEFT_CENTER, 115.1, 'PAQUITO S. YU MEMORIAL NATIONAL HIGH SCHOOL', BOLD, 6.5)
    _ctext(c, LEFT_CENTER, 126.7, "LEARNER'S PERFORMANCE REPORT", BOLD)
    _ctext(c, LEFT_CENTER, 135.5, f"School Year {ctx['school_year'].name if ctx['school_year'] else '__________'}")

    # Learner information: label + underlined value pairs.
    info_rows = [
        (153.1, 154.7, [
            ('Name:', 48.6, 82.6, 229.1, ctx['learner_name']),
            ('Age:', 230.6, 259.4, 289.9, str(ctx['age'])),
            ('Sex:', 291.4, 322.8, 373.2, ctx['sex']),
        ]),
        (161.9, 163.5, [
            ('LRN:', 48.6, 82.6, 170.8, ctx['lrn']),
            ('Grade:', 230.6, 259.4, 289.9, str(ctx['grade_level'])),
            ('Section:', 291.4, 322.8, 373.2, ctx['section_name']),
        ]),
    ]
    for baseline, line_y, fields in info_rows:
        for label, lx, u0, u1, value in fields:
            _text(c, lx, baseline, label)
            _hline(c, u0, u1, line_y)
            if value:
                _ctext(c, (u0 + u1) / 2, baseline, value)
    _text(c, 48.6, 170.7, 'Track (SHS only):')
    _hline(c, 109.8, 201.2, 172.3)

    _text(c, 48.6, 188.3, 'Dear Parents,')
    _text(c, 84.2, 197.1, "This Performance Report presents your child's progress and achievement")
    _text(c, 48.6, 205.9, 'in the different learning areas.')
    _text(c, 84.2, 214.7, 'The school welcomes you to reach out should you wish to know more about your')
    _text(c, 48.6, 223.5, "child's learning and performance.")

    # School Head / Adviser signature lines.
    _hline(c, 47.0, 201.2, 242.7)
    _hline(c, 229.0, 373.2, 242.7)
    _ctext(c, 124.1, 241.1, ctx['school_head_name'], BOLD)
    _ctext(c, 301.1, 241.1, ctx['adviser_name'], BOLD)
    _ctext(c, 124.1, 249.9, 'School Head')
    _ctext(c, 301.1, 249.9, 'Adviser')

    _draw_grades_table(c, ctx)
    _draw_descriptors(c, ctx)


def _draw_grades_table(c, ctx):
    rows = ctx['rows']
    term_labels = ctx['term_labels']

    data_top = GT_TOP + GT_HDR1 + GT_HDR2
    data_bottom = GT_BOTTOM - GT_AVG_H
    row_h = (data_bottom - data_top) / max(len(rows), 1)

    _box(c, GT_X[0], GT_TOP, GT_X[-1], GT_BOTTOM, width=0.6)
    _vline(c, GT_X[1], GT_TOP, data_bottom)
    _vline(c, GT_X[2], GT_TOP + GT_HDR1, data_bottom)
    _vline(c, GT_X[3], GT_TOP + GT_HDR1, data_bottom)
    _vline(c, GT_X[4], GT_TOP, GT_BOTTOM)
    _vline(c, GT_X[5], GT_TOP, GT_BOTTOM)
    _hline(c, GT_X[0], GT_X[-1], GT_TOP + GT_HDR1 + GT_HDR2)
    _hline(c, GT_X[1], GT_X[4], GT_TOP + GT_HDR1)
    _hline(c, GT_X[0], GT_X[-1], data_bottom)

    hdr_mid = GT_TOP + (GT_HDR1 + GT_HDR2) / 2
    _ctext(c, (GT_X[0] + GT_X[1]) / 2, hdr_mid + 2.3, 'Learning Areas', BOLD)
    _ctext(c, (GT_X[1] + GT_X[4]) / 2, GT_TOP + GT_HDR1 / 2 + 2.3, 'TERM', BOLD)
    _ctext(c, (GT_X[4] + GT_X[5]) / 2, hdr_mid - 2.6, 'Final', BOLD)
    _ctext(c, (GT_X[4] + GT_X[5]) / 2, hdr_mid + 6.3, 'Grade', BOLD)
    _ctext(c, (GT_X[5] + GT_X[6]) / 2, hdr_mid + 2.3, 'Remarks', BOLD)
    for i, label in enumerate(term_labels[:3]):
        _ctext(c, (GT_X[1 + i] + GT_X[2 + i]) / 2, GT_TOP + GT_HDR1 + GT_HDR2 / 2 + 2.3, label, BOLD)

    for i, row in enumerate(rows):
        top = data_top + i * row_h
        baseline = top + row_h / 2 + 2.6
        if i > 0:
            _hline(c, GT_X[0], GT_X[-1], top)
        if row['style'] == 'sub':
            _text(c, 48.5, baseline, row['name'], ITAL, 6.5)
        else:
            _text(c, 48.6, baseline, row['name'])
        for j, value in enumerate(row['term_cells'][:3]):
            _ctext(c, (GT_X[1 + j] + GT_X[2 + j]) / 2, baseline, _fmt(value))
        _ctext(c, (GT_X[4] + GT_X[5]) / 2, baseline, _fmt(row['final']), BOLD)
        _ctext(c, (GT_X[5] + GT_X[6]) / 2, baseline, row['remarks'])

    avg_mid = data_bottom + GT_AVG_H / 2
    _ctext(c, (GT_X[0] + GT_X[4]) / 2, avg_mid + 2.9, 'General Average', BOLDITAL, 8.3)
    _ctext(c, (GT_X[4] + GT_X[5]) / 2, avg_mid + 2.6, _fmt(ctx['general_average']), BOLD)
    _ctext(c, (GT_X[5] + GT_X[6]) / 2, avg_mid + 2.6, ctx['general_average_remarks'], BOLD)


def _draw_descriptors(c, ctx):
    _text(c, 48.7, 469.4, 'PERFORMANCE DESCRIPTORS', BOLD)
    cols = (126.0, 198.5, 291.0)
    _ctext(c, cols[0], 478.2, 'Grading Scale', BOLD)
    _ctext(c, cols[1], 478.2, 'Descriptors', BOLD)
    _ctext(c, cols[2], 478.2, 'Remarks', BOLD)
    for i, (scale, descriptor, remarks) in enumerate(ctx['descriptor_rows']):
        baseline = 487.0 + i * 8.8
        _ctext(c, cols[0], baseline, scale)
        _ctext(c, cols[1], baseline, descriptor)
        _ctext(c, cols[2], baseline, remarks)


def _draw_right_panel(c, ctx):
    _box(c, 422.5, 26.7, 773.5, 533.2, width=1.2)

    # Attendance grid (no attendance register in the system: cells stay blank).
    _box(c, AT_X[0], AT_Y[0], AT_X[-1], AT_Y[-1])
    for x in AT_X[1:-1]:
        _vline(c, x, AT_Y[0], AT_Y[-1])
    for y in AT_Y[1:-1]:
        _hline(c, AT_X[0], AT_X[-1], y)
    _ctext(c, (AT_X[0] + AT_X[1]) / 2, 52.1, 'Month', BOLD)
    for i, month in enumerate(AT_MONTHS):
        _ctext(c, (AT_X[1 + i] + AT_X[2 + i]) / 2, 52.1, month, BOLD)
    _ctext(c, (AT_X[12] + AT_X[13]) / 2, 52.1, 'Total', BOLD)
    for i, (line1, line2) in enumerate(AT_ROWS):
        top = AT_Y[1 + i]
        _ctext(c, (AT_X[0] + AT_X[1]) / 2, top + 7.0, line1, BOLD)
        _ctext(c, (AT_X[0] + AT_X[1]) / 2, top + 15.9, line2, BOLD)

    _ctext(c, RIGHT_CENTER, 126.7, "TEACHER'S COMMENTS / REMARKS", BOLD)
    labels = ctx['term_full_labels']
    box_top, box_bottom = 128.3, 233.9
    seg = (box_bottom - box_top) / len(labels)
    _box(c, 435.7, box_top, 760.4, box_bottom)
    for i, label in enumerate(labels):
        top = box_top + i * seg
        if i > 0:
            _hline(c, 435.7, 760.4, top)
        _text(c, 437.4, top + 7.5, label, BOLD)

    _ctext(c, RIGHT_CENTER, 249.4, "PARENT/S GUARDIAN'S SIGNATURE", BOLD)
    for i, label in enumerate(labels):
        baseline = 264.1 + i * 14.3
        _text(c, 498.9, baseline, label, BOLD)
        _hline(c, 527.2, 719.0, baseline + 1.7)

    _ctext(c, RIGHT_CENTER, 317.8, 'CERTIFICATE OF TRANSFER', BOLD)
    _text(c, 437.2, 335.2, 'This is to certify that the above-named learner has satisfactorily completed the requirements')
    _text(c, 437.2, 349.4, 'for the grade level indicated.')
    _text(c, 437.2, 377.8, 'Admitted to Grade:')
    _hline(c, 505.9, 548.5, 379.4)
    _text(c, 437.2, 392.0, 'Eligible for Admission to Grade:')
    _hline(c, 548.5, 633.8, 393.55)
    _text(c, 437.2, 420.4, 'Approved:')
    _hline(c, 612.4, 760.5, 422.0)
    _ctext(c, 686.45, 420.4, ctx['adviser_name'], BOLD)
    _ctext(c, 686.45, 429.8, 'Adviser')
    _hline(c, 435.6, 591.2, 444.6)
    _ctext(c, 513.4, 443.0, ctx['school_head_name'], BOLD)
    _ctext(c, 513.4, 451.8, 'School Head')

    _ctext(c, RIGHT_CENTER, 468.9, 'CANCELLATION OF ELIGIBILITY TO TRANSFER', BOLD)
    _text(c, 437.2, 478.2, 'Admitted in:')
    _hline(c, 484.5, 612.5, 479.8)
    _text(c, 614.0, 478.2, 'Date:')
    _hline(c, 633.7, 719.0, 479.8)
    _hline(c, 435.6, 591.2, 506.2)
    _ctext(c, 513.4, 504.6, ctx['school_head_name'], BOLD)
    _ctext(c, 513.4, 513.4, 'School Head')


def build_report_card_pdf(buffer, ctx):
    c = pdf_canvas.Canvas(buffer, pagesize=(PAGE_W, PAGE_H))
    c.setTitle(f"Learner's Performance Report - {ctx['learner_name']}")
    _draw_left_panel(c, ctx)
    _draw_right_panel(c, ctx)
    c.showPage()
    c.save()
