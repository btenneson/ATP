#!/usr/bin/env python3
"""
Generate predator5_commands.pdf: an 8-step guide to running Predator_5
with exact terminal commands for Windows PowerShell.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Preformatted, Table, TableStyle
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER

def create_pdf():
    doc = SimpleDocTemplate(
        "predator5_commands.pdf",
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
    )

    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    story.append(Paragraph("Predator_5 Quick Start", title_style))

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#444444'),
        spaceAfter=12,
        alignment=TA_CENTER,
    )
    story.append(Paragraph("8 Steps to Train and Evaluate Proof-Search Policies", subtitle_style))
    story.append(Spacer(1, 0.2*inch))

    # Section style
    heading_style = ParagraphStyle(
        'StepHeading',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=colors.HexColor('#000080'),
        spaceAfter=6,
        spaceBefore=8,
        fontName='Helvetica-Bold',
    )

    # Code style
    code_style = ParagraphStyle(
        'Code',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=9,
        textColor=colors.HexColor('#333333'),
        leftIndent=0.3*inch,
        backColor=colors.HexColor('#f5f5f5'),
        spaceAfter=8,
    )

    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
    )

    # Step 1
    story.append(Paragraph("<b>Step 1: Open PowerShell</b>", heading_style))
    story.append(Paragraph(
        "Press <b>Win + R</b>, type <b>powershell</b>, and press Enter. You will see a prompt like <b>PS C:\\Users\\YourName></b>",
        normal_style
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 2
    story.append(Paragraph("<b>Step 2: Navigate to the outputs folder</b>", heading_style))
    story.append(Preformatted(
        "cd C:\\Users\\12096\\AppData\\Roaming\\Claude\\local-agent-mode-sessions\\8db2ec26-c9d2-4bf4-9004-f935cf388709\\edb6663a-5eca-424a-a8c4-7d780d1fe796\\local_3ee9fec9-367f-4e0c-9d1f-418738530a19\\outputs",
        code_style
    ))
    story.append(Paragraph(
        "Verify you are there: <b>ls</b> should list <b>predator5.py</b>",
        normal_style
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 3
    story.append(Paragraph("<b>Step 3: Check the environment</b>", heading_style))
    story.append(Preformatted("python predator5.py doctor", code_style))
    story.append(Paragraph(
        "Output shows Python version and whether numpy/sklearn are installed. "
        "No action needed if sklearn is missing for step 5; logistic regression works without it.",
        normal_style
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 4
    story.append(Paragraph("<b>Step 4: Harvest the ground truth</b>", heading_style))
    story.append(Preformatted(
        "python predator5.py harvest --depth 4 --edge-cap 15 --max-size 14",
        code_style
    ))
    story.append(Paragraph(
        "Runs breadth-first sweep. Prints geodesic distances (least <i>m</i> with <i>w</i> ∈ <i>p</i><sub>m</sub>) for 63 targets. "
        "Keep the output — you will need the held-out target list for later steps.",
        normal_style
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 5
    story.append(Paragraph("<b>Step 5: Train the logistic ranker</b>", heading_style))
    story.append(Preformatted("python predator5.py train --model logistic --depth 4 --seed 0", code_style))
    story.append(Paragraph(
        "Prints 12 fitted weights. Positive weight: higher score → more likely on-geodesic. "
        "Negative: the reverse.",
        normal_style
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 6
    story.append(Paragraph("<b>Step 6: (Optional) Train the random forest</b>", heading_style))
    story.append(Paragraph(
        "First, install scikit-learn if you haven't:",
        normal_style
    ))
    story.append(Preformatted("pip install scikit-learn", code_style))
    story.append(Paragraph(
        "Then train:",
        normal_style
    ))
    story.append(Preformatted(
        "python predator5.py train --model forest --depth 4 --seed 0 --n-estimators 300 --max-depth 12 --min-samples-leaf 4",
        code_style
    ))
    story.append(Paragraph(
        "Prints Gini importances for each feature.",
        normal_style
    ))
    story.append(Spacer(1, 0.1*inch))

    # Page break before step 7
    story.append(PageBreak())

    # Step 7
    story.append(Paragraph("<b>Step 7: Compare both models on held-out targets</b>", heading_style))
    story.append(Paragraph(
        "<b>This is the command that matters.</b> It fits logistic and forest on training targets, "
        "then evaluates both in reorder and prune modes against breadth-first search on held-out targets.",
        normal_style
    ))
    story.append(Preformatted(
        "python predator5.py compare --depth 4 --edge-cap 12 --max-size 14 --budget 150 --lam 0.5 -k 4 --test-frac 0.35 --n-estimators 60 --max-depth 8 --out results.json",
        code_style
    ))
    story.append(Paragraph(
        "Output appears both on screen and in <b>results.json</b>.",
        normal_style
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 8
    story.append(Paragraph("<b>Step 8: Verify stability across random splits</b>", heading_style))
    story.append(Paragraph(
        "Runs step 7 with five different random seeds. If the speedup swings wildly, "
        "the 19-target held-out set is too small.",
        normal_style
    ))
    story.append(Preformatted(
        "for ($S=0; $S -lt 5; $S++) { python predator5.py compare --depth 4 --seed $S --budget 150 --n-estimators 40 | Select-String \"logistic reorder\" }",
        code_style
    ))
    story.append(Spacer(1, 0.15*inch))

    # Additional bash loops section
    story.append(Paragraph("<b>Bonus: Sweep the interpolation knob (λ)</b>", heading_style))
    story.append(Paragraph(
        "At λ=0 every row must collapse to BFS; if it does not, the depth term is miswired. "
        "As λ grows, expansions should fall and then rise as the search starts diving.",
        normal_style
    ))
    story.append(Preformatted(
        "for L in 0 0.25 0.5 1 2 4 8; do echo \"=== lambda = $L ===\"; python predator5.py compare --depth 4 --lam $L --budget 150 --n-estimators 40 --out \"lam_$L.json\" | grep -A8 \"HELD-OUT\"; done",
        code_style
    ))
    story.append(Spacer(1, 0.1*inch))

    # Widen the sweep section
    story.append(Paragraph("<b>Bonus: Widen the sweep for more targets</b>", heading_style))
    story.append(Paragraph(
        "Deeper sweep, more targets, bigger held-out set. Slower — the state count grows fast.",
        normal_style
    ))
    story.append(Preformatted(
        "python predator5.py compare --depth 5 --edge-cap 12 --max-size 14 --budget 400 --lam 0.5 -k 4 --test-frac 0.3 --n-estimators 60 --max-depth 8 --out deep.json",
        code_style
    ))
    story.append(Spacer(1, 0.2*inch))

    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
        spaceAfter=0,
    )
    story.append(Paragraph(
        "<i>Predator_5 v5.0 — Learned Search Policies over Computed Geodesics</i>",
        footer_style
    ))

    doc.build(story)
    print("✓ predator5_commands.pdf created (8 steps + bonus commands)")

if __name__ == "__main__":
    create_pdf()
