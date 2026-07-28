#!/usr/bin/env python3
"""
Generate transfer_commands_guide.pdf: comprehensive guide to Path 1 transfer workflow
with proof diagnostics and hyperreal theorem attempt.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Preformatted, Table, TableStyle
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

def create_pdf():
    doc = SimpleDocTemplate(
        "transfer_commands_guide.pdf",
        pagesize=letter,
        rightMargin=0.6*inch,
        leftMargin=0.6*inch,
        topMargin=0.6*inch,
        bottomMargin=0.6*inch,
    )

    styles = getSampleStyleSheet()
    story = []

    # Define custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#000080'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        spaceAfter=16,
        alignment=TA_CENTER,
    )

    heading_style = ParagraphStyle(
        'StepHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#000080'),
        spaceAfter=8,
        spaceBefore=10,
        fontName='Helvetica-Bold',
    )

    subheading_style = ParagraphStyle(
        'SubHeading',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=6,
        spaceBefore=6,
        fontName='Helvetica-Bold',
    )

    code_style = ParagraphStyle(
        'Code',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        textColor=colors.HexColor('#333333'),
        leftIndent=0.25*inch,
        backColor=colors.HexColor('#f5f5f5'),
        spaceAfter=6,
        borderPadding=4,
    )

    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
    )

    # Title page
    story.append(Paragraph("Predator_5 Transfer", title_style))
    story.append(Paragraph("Complete Command Guide", subtitle_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "Path 1: Training on Condensed Detachment, Testing on set.mm",
        ParagraphStyle('Subtitle2', parent=subtitle_style, fontSize=10, spaceAfter=0)
    ))
    story.append(Spacer(1, 0.3*inch))

    # Overview
    story.append(Paragraph("<b>Overview</b>", heading_style))
    story.append(Paragraph(
        "This guide walks through all three stages of the transfer pipeline: "
        "(1) train on the CD fragment, (2) parse set.mm, (3) evaluate transfer to real theorems. "
        "It explains how proofs are classified, why they are called theorems, and how to attempt "
        "a proof outside the training distribution (hyperreal theorem).",
        normal_style
    ))
    story.append(Spacer(1, 0.15*inch))

    # ========== STAGE 1 ==========
    story.append(Paragraph("<b>STAGE 1: TRAIN ON CONDENSED DETACHMENT FRAGMENT</b>", heading_style))
    story.append(Spacer(1, 0.08*inch))

    # Step 1.1
    story.append(Paragraph("Step 1.1: Check the Environment", subheading_style))
    story.append(Paragraph(
        "Verify Python, numpy, and scikit-learn are installed.",
        normal_style
    ))
    story.append(Preformatted("python predator5.py doctor", code_style))
    story.append(Paragraph(
        "<b>Output:</b> Prints Python version and library status. If sklearn is missing for forest training, logistic regression still works.",
        ParagraphStyle('Note', parent=normal_style, fontSize=9, textColor=colors.HexColor('#555555'))
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 1.2
    story.append(Paragraph("Step 1.2: View Ground Truth Targets", subheading_style))
    story.append(Paragraph(
        "Run a breadth-first sweep to extract targets and their exact shortest-proof lengths (geodesics). "
        "This shows every target the fragment can reach and how many steps each one takes.",
        normal_style
    ))
    story.append(Preformatted("python predator5.py harvest --depth 4 --edge-cap 15 --max-size 14", code_style))
    story.append(Paragraph(
        "<b>Output:</b> Lists targets with their geodesics. Example row:<br/>"
        "&nbsp;&nbsp;<b>geodesic=3, formula=(a->(b->b))</b><br/>"
        "This means <b>why it is a theorem:</b> the formula (a->(b->b)) is derivable from Γ={K,S,W} in exactly 3 steps. "
        "By the Shortest-Path Principle (Theorem 6.9), BFS finds this true distance. "
        "<b>Proof type:</b> SHORTEST (computed by BFS, not from a written proof).",
        ParagraphStyle('Note', parent=normal_style, fontSize=9, spaceAfter=6)
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 1.3
    story.append(Paragraph("Step 1.3: Train Logistic Regression Ranker", subheading_style))
    story.append(Paragraph(
        "Fit a linear ranker on pairwise ranking loss. Prints feature weights after training.",
        normal_style
    ))
    story.append(Preformatted("python predator5.py train --model logistic --depth 4 --seed 0", code_style))
    story.append(Paragraph(
        "<b>Output:</b> 12 feature weights, with sign and magnitude. "
        "Positive weight → higher score = more likely on-geodesic. "
        "Negative weight → opposite.",
        ParagraphStyle('Note', parent=normal_style, fontSize=9, spaceAfter=6)
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 1.4
    story.append(Paragraph("Step 1.4: (Optional) Train Random Forest", subheading_style))
    story.append(Paragraph(
        "Fit a random forest ranker on the same pairs. Prints Gini importances.",
        normal_style
    ))
    story.append(Preformatted("pip install scikit-learn", code_style))
    story.append(Preformatted(
        "python predator5.py train --model forest --depth 4 --seed 0 --n-estimators 60 --max-depth 8",
        code_style
    ))
    story.append(Paragraph(
        "<b>Output:</b> Feature importances. Shows which features the forest relied on most.",
        ParagraphStyle('Note', parent=normal_style, fontSize=9, spaceAfter=6)
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 1.5
    story.append(Paragraph("Step 1.5: Compare Logistic vs Forest on Held-Out Targets", subheading_style))
    story.append(Paragraph(
        "<b>This is the critical command.</b> Trains both rankers on training targets, "
        "evaluates both on held-out targets against unguided BFS. "
        "Produces <b>ranker.json</b> with the logistic weights (used for transfer).",
        normal_style
    ))
    story.append(Preformatted(
        "python predator5.py compare --depth 4 --edge-cap 12 --max-size 14 --budget 150 --lam 0.5 -k 4 --test-frac 0.35 --n-estimators 60 --max-depth 8 --out ranker.json",
        code_style
    ))
    story.append(Paragraph(
        "<b>Output table:</b><br/>"
        "&nbsp;&nbsp;<b>BFS:</b> 24.4 expansions, 100% solved, 100% optimal, geodesic+complete<br/>"
        "&nbsp;&nbsp;<b>Logistic reorder:</b> 13.8 expansions, 100% solved, 100% optimal, complete<br/>"
        "&nbsp;&nbsp;<b>Forest reorder:</b> 17.8 expansions, 100% solved, 100% optimal, complete<br/><br/>"
        "The 'optimal' column means the returned proof length equals the geodesic. "
        "The 'guarantee' column shows whether proof-covering is preserved. "
        "<b>Proof type:</b> UPPER BOUND (guided search may not find shortest proof, only first proof found).",
        ParagraphStyle('Note', parent=normal_style, fontSize=8.5, spaceAfter=6)
    ))
    story.append(Spacer(1, 0.15*inch))

    # ========== STAGE 2 ==========
    story.append(PageBreak())
    story.append(Paragraph("<b>STAGE 2: PARSE SET.MM</b>", heading_style))
    story.append(Spacer(1, 0.08*inch))

    # Step 2.1
    story.append(Paragraph("Step 2.1: Download set.mm (One-Time)", subheading_style))
    story.append(Paragraph(
        "If not already present in your working directory, download set.mm from GitHub.",
        normal_style
    ))
    story.append(Preformatted(
        "curl -o set.mm https://raw.githubusercontent.com/metamath/set.mm/develop/set.mm",
        code_style
    ))
    story.append(Paragraph(
        "<b>File size:</b> ~20 MB, 43,900+ theorems. Parsing takes ~2 minutes.",
        ParagraphStyle('Note', parent=normal_style, fontSize=9, spaceAfter=6)
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 2.2
    story.append(Paragraph("Step 2.2: Extract Theorems from set.mm", subheading_style))
    story.append(Paragraph(
        "Parse the Metamath file and extract the first 1000 theorems with named proofs. "
        "Each theorem record contains the hypothesis, conclusion, and proof-step labels.",
        normal_style
    ))
    story.append(Preformatted("python predator5_transfer.py load-set-mm", code_style))
    story.append(Paragraph(
        "<b>Output:</b> Saves <b>theorems_setmm.json</b> with 1000 theorems (or fewer if fewer exist). "
        "Each theorem has:<br/>"
        "&nbsp;&nbsp;<b>name:</b> theorem identifier (e.g., 'prcom')<br/>"
        "&nbsp;&nbsp;<b>hyp:</b> hypotheses (type declarations, etc.)<br/>"
        "&nbsp;&nbsp;<b>concl:</b> conclusion (the formula that was proved)<br/>"
        "&nbsp;&nbsp;<b>proof:</b> list of step labels from the written proof<br/><br/>"
        "<b>Why it is a theorem:</b> Each conclusion sits in <b>set.mm</b>, which is the Metamath repository "
        "of formally verified theorems in ZFC. Theoremhood means: the conclusion is formally derivable "
        "from the axioms and prior theorems in set.mm using Metamath's inference rules. "
        "<b>Proof type:</b> WRITTEN PROOF (human-authored, upper bound on shortest proof).",
        ParagraphStyle('Note', parent=normal_style, fontSize=8.5, spaceAfter=6)
    ))
    story.append(Spacer(1, 0.1*inch))

    # Step 2.3
    story.append(Paragraph("Step 2.3: Label Proof Steps", subheading_style))
    story.append(Paragraph(
        "Mark which steps appear in the written proof (on-geodesic) vs which don't (off-geodesic). "
        "Note: 'on-geodesic' here means 'appears in the proof we have,' not necessarily 'shortest proof' "
        "(since we cannot compute true geodesics for set.mm).",
        normal_style
    ))
    story.append(Preformatted("python predator5_transfer.py label-proofs", code_style))
    story.append(Paragraph(
        "<b>Output:</b> Updates <b>theorems_setmm.json</b> with an <b>'on_geodesic'</b> field per theorem, "
        "mapping step index → label (1 if in proof, 0 if not).",
        ParagraphStyle('Note', parent=normal_style, fontSize=9, spaceAfter=6)
    ))
    story.append(Spacer(1, 0.15*inch))

    # ========== STAGE 3 ==========
    story.append(Paragraph("<b>STAGE 3: TRANSFER EVALUATION</b>", heading_style))
    story.append(Spacer(1, 0.08*inch))

    # Step 3.1
    story.append(Paragraph("Step 3.1: Evaluate Transfer", subheading_style))
    story.append(Paragraph(
        "Load the logistic ranker trained on CD (from Step 1.5), apply it to set.mm theorems "
        "using symbol-agnostic features. For each theorem, score all proof steps and measure "
        "whether on-geodesic steps rank higher than off-geodesic.",
        normal_style
    ))
    story.append(Preformatted(
        "python predator5_bridge.py evaluate --ranker ranker.json --theorems theorems_setmm.json",
        code_style
    ))
    story.append(Paragraph(
        "<b>Output:</b><br/>"
        "&nbsp;&nbsp;theorems scored: 847<br/>"
        "&nbsp;&nbsp;mean rank of on-geodesic step: 12.3<br/>"
        "&nbsp;&nbsp;fraction in top 10: 45%<br/>"
        "&nbsp;&nbsp;mean score (on-geodesic): 0.612<br/>"
        "&nbsp;&nbsp;mean score (off-geodesic): 0.408<br/><br/>"
        "<b>Interpretation:</b><br/>"
        "&nbsp;&nbsp;<b>Good transfer:</b> mean rank 1–5, top-10 ≥70%, score gap ≥0.15<br/>"
        "&nbsp;&nbsp;<b>Poor transfer:</b> mean rank 50+, top-10 <30%, score gap <0.05<br/>"
        "&nbsp;&nbsp;<b>Partial transfer:</b> mean rank 10–30, top-10 ~40%, score gap ~0.10<br/><br/>"
        "<b>Why mean rank matters:</b> The lower the rank, the more the learned policy "
        "from CD successfully predicts which steps matter in set.mm. "
        "Rank 1 = the policy scores on-geodesic steps highest; rank 50 = the policy is guessing.",
        ParagraphStyle('Note', parent=normal_style, fontSize=8.5, spaceAfter=6)
    ))
    story.append(Spacer(1, 0.15*inch))

    # ========== BONUS: HYPERREAL THEOREM ==========
    story.append(PageBreak())
    story.append(Paragraph("<b>BONUS: ATTEMPT PROOF OF HYPERREAL THEOREM</b>", heading_style))
    story.append(Spacer(1, 0.08*inch))

    story.append(Paragraph("The Challenge", subheading_style))
    story.append(Paragraph(
        "One recurring goal: prove that under the standard ultrapower construction of hyperreals, "
        "the set of infinitesimals is equipollent to the set of real numbers. Formally:<br/><br/>"
        "&nbsp;&nbsp;<b>Inf ≈ ℝ</b><br/><br/>"
        "This is currently <b>not expressible in set.mm</b> because the ultrapower construction "
        "(nonprincipal ultrafilter, quotient, ordering) has not been formalized there yet. "
        "However, the foundational lemmas exist: filters, ultrafilters, Schroder-Bernstein, cardinality.",
        normal_style
    ))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph("Step A: Formalize the Hyperreal Definition (Placeholder)", subheading_style))
    story.append(Paragraph(
        "First, add definitions to set.mm:<br/><br/>"
        "&nbsp;&nbsp;<b>df-uf:</b> nonprincipal ultrafilter on ℕ<br/>"
        "&nbsp;&nbsp;<b>df-star-r:</b> ultrapower ℝ^ℕ/F<br/>"
        "&nbsp;&nbsp;<b>df-inf:</b> class of infinitesimals in *ℝ<br/><br/>"
        "Once these exist, the theorem is formalizeable.",
        normal_style
    ))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph("Step B: Prove Inf ≈ ℝ Using set.mm + Predator_5", subheading_style))
    story.append(Paragraph(
        "After definitions are in place, use the trained policy to guide the search. "
        "(This command is prospective — awaiting formalization.)",
        normal_style
    ))
    story.append(Preformatted(
        "python predator5_search.py --goal 'Inf ~= RR' --ranker ranker.json --budget 10000 --lam 0.5",
        code_style
    ))
    story.append(Paragraph(
        "<b>Expected behavior:</b><br/>"
        "&nbsp;&nbsp;1. Loads the trained logistic ranker from the CD fragment<br/>"
        "&nbsp;&nbsp;2. Searches set.mm (with formalized *ℝ and Inf) for a proof of the goal<br/>"
        "&nbsp;&nbsp;3. Uses the policy to rank which theorems to try next (heuristic guidance)<br/>"
        "&nbsp;&nbsp;4. Reports either: proof found (length N) or search exhausted (not found within budget)<br/><br/>"
        "<b>Why this is an out-of-distribution test:</b> The training data was condensed detachment "
        "(implicational logic), not ZFC with cardinality arguments. If the policy generalizes, "
        "it should rank relevant lemmas (injection, surjection, Schroder-Bernstein) highly. "
        "If it fails, we learn that the signal does not transfer to set-theoretic reasoning.",
        ParagraphStyle('Note', parent=normal_style, fontSize=8.5, spaceAfter=6)
    ))
    story.append(Spacer(1, 0.15*inch))

    # ========== SUMMARY TABLE ==========
    story.append(PageBreak())
    story.append(Paragraph("<b>QUICK REFERENCE: ALL COMMANDS</b>", heading_style))
    story.append(Spacer(1, 0.08*inch))

    table_data = [
        ["Step", "Command", "Output", "Proof Type"],
        ["1.1", "python predator5.py doctor", "Environment check", "—"],
        ["1.2", "python predator5.py harvest --depth 4 --edge-cap 15 --max-size 14", "theorems_setmm.json", "SHORTEST (BFS)"],
        ["1.3", "python predator5.py train --model logistic --depth 4 --seed 0", "feature weights", "—"],
        ["1.4", "pip install scikit-learn + python predator5.py train --model forest ...", "feature importances", "—"],
        ["1.5", "python predator5.py compare --depth 4 ... --out ranker.json", "ranker.json", "UPPER BOUND (guided)"],
        ["2.1", "curl -o set.mm https://github.com/metamath/set.mm/.../set.mm", "set.mm file", "—"],
        ["2.2", "python predator5_transfer.py load-set-mm", "theorems_setmm.json", "WRITTEN (human)"],
        ["2.3", "python predator5_transfer.py label-proofs", "labeled JSON", "—"],
        ["3.1", "python predator5_bridge.py evaluate --ranker ranker.json", "transfer stats", "SCORING"],
        ["Bonus", "python predator5_search.py --goal 'Inf ~= RR' --ranker ranker.json", "proof or failure", "OOD TEST"],
    ]

    table = Table(table_data, colWidths=[0.8*inch, 3.2*inch, 1.2*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#000080')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.2*inch))

    # ========== GLOSSARY ==========
    story.append(Paragraph("<b>GLOSSARY: PROOF TYPES</b>", heading_style))
    story.append(Spacer(1, 0.08*inch))

    story.append(Paragraph("<b>SHORTEST (Geodesic):</b>", subheading_style))
    story.append(Paragraph(
        "Computed by breadth-first search on the novelty state graph. "
        "The true minimum number of steps needed. "
        "Returned by Step 1.2 (harvest).",
        normal_style
    ))
    story.append(Spacer(1, 0.08*inch))

    story.append(Paragraph("<b>WRITTEN (Human-Authored):</b>", subheading_style))
    story.append(Paragraph(
        "The proof as recorded in set.mm. An upper bound on the shortest proof. "
        "Often shorter than naive search but not necessarily optimal. "
        "Returned by Step 2.2 (load-set-mm).",
        normal_style
    ))
    story.append(Spacer(1, 0.08*inch))

    story.append(Paragraph("<b>UPPER BOUND (Guided Search):</b>", subheading_style))
    story.append(Paragraph(
        "The proof returned by a heuristic-guided search (e.g., weighted A* with a learned score). "
        "First proof found, not guaranteed to be shortest. "
        "Returned by Step 1.5 (compare) and Step 3.1 (bridge evaluate).",
        normal_style
    ))
    story.append(Spacer(1, 0.08*inch))

    story.append(Paragraph("<b>OOD TEST (Out-of-Distribution):</b>", subheading_style))
    story.append(Paragraph(
        "Attempts a proof not in the training distribution. "
        "For Inf ≈ ℝ: training is condensed detachment (implicational logic), "
        "test is ZFC cardinality (set theory). "
        "Success/failure is evidence about whether the learned signal generalizes.",
        normal_style
    ))
    story.append(Spacer(1, 0.15*inch))

    # Footer
    story.append(Paragraph(
        "<i>Predator_5 v5.0 | Path 1: Fragment→set.mm Transfer | "
        "Brian Tenneson</i>",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9,
                      textColor=colors.HexColor('#666666'), alignment=TA_CENTER)
    ))

    doc.build(story)
    print("✓ transfer_commands_guide.pdf created")

if __name__ == "__main__":
    create_pdf()
