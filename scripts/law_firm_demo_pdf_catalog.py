"""
Shared Sterling & Vale LLP demo PDF definitions and writer (fpdf2).

Used by:
  - scripts/seed_law_firm_rag.py (index into DB)
  - scripts/write_demo_pdf_assets_to_docs.py (export copies under docs/demo/...)
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

# Matches LAW_FIRM_ORG_SLUG in seed_law_firm.py default
DEMO_ORGANIZATION_SLUG = "sterling-vale-llp"

# Folder names under docs/demo/organizations/<org>/workspaces/<slug>/
WORKSPACE_DIR_SLUGS: dict[str, str] = {
    "General": "general",
    "Litigation & Disputes": "litigation-disputes",
    "Corporate & Transactions": "corporate-transactions",
    "Knowledge & Precedents": "knowledge-precedents",
    "Client Intake & Conflicts": "client-intake-conflicts",
}


def workspace_dir_slug(workspace_name: str) -> str:
    return WORKSPACE_DIR_SLUGS.get(
        workspace_name,
        workspace_name.lower().replace(" & ", "-").replace(" ", "-").replace("&", "and"),
    )


# Rich ASCII-only text so fpdf Helvetica and Ollama embeddings behave predictably.
DEMO_PDFS: list[dict] = [
    {
        "workspace": "General",
        "filename": "Firm_Operations_and_Billing_Policy.pdf",
        "title": "Firm Operations - Billing and Retainers",
        "body": """
# Purpose of the General workspace

The purpose of the General workspace is cross-practice coordination: firm-wide notices,
administrative templates, and links to policies that apply across Litigation, Corporate,
and Client Intake. Ask operational questions here when answers should be grounded in shared
firm policy rather than a single matter room.

# Retainers and billing

Billable work may begin only after a countersigned engagement letter and cleared retainer per the
finance team schedule. Time entries must reference a matter code and workspace tag.

# Cross-practice coordination

Use the General workspace for firm-wide notices, administrative templates, and links to
policies that apply across Litigation, Corporate, and Client Intake.

# Sterling Vale reminder

Route escalations to the managing partner when a matter touches more than one practice group.
""".strip(),
        "questions": [
            {
                "q": "When may billable work begin according to the billing policy?",
                "a": "Only after a countersigned engagement letter and cleared retainer.",
            },
            {
                "q": "What is the purpose of the General workspace?",
                "a": "Cross-practice coordination: firm-wide notices, templates, and policy links.",
            },
        ],
    },
    {
        "workspace": "Litigation & Disputes",
        "filename": "Sterling_Vale_MTD_Playbook.pdf",
        "title": "Motion to Dismiss - Internal Playbook",
        "body": """
# Federal MTD checklist

Before filing a Rule 12(b)(6) motion, verify subject-matter jurisdiction under 28 U.S.C. 1331
and confirm removal timeliness if the case arrived from state court.

# Standard of review

Courts treat the complaint as true on a motion to dismiss. Cite Ashcroft v. Iqbal for
plausible-claim pleading. Map each element of the cause of action to numbered paragraphs
in the complaint.

# Sterling Vale practice notes

Attach the controlling circuit split memo from the Knowledge workspace. Calendar a reply
brief deadline 14 days after opposition. Escalate to the litigation partner if the matter
involves a parallel regulatory investigation.
""".strip(),
        "questions": [
            {
                "q": "What statute do we cite for federal subject-matter jurisdiction in the MTD playbook?",
                "a": "28 U.S.C. 1331 is listed for subject-matter jurisdiction before filing a Rule 12(b)(6) motion.",
            },
            {
                "q": "How many days after opposition do we calendar the reply brief?",
                "a": "The playbook says to calendar the reply brief deadline 14 days after opposition.",
            },
        ],
    },
    {
        "workspace": "Corporate & Transactions",
        "filename": "Vendor_MSA_Indemnity_Reference.pdf",
        "title": "Vendor MSA - Indemnity and Carve-Outs",
        "body": """
# Indemnity structure

Third-party indemnity survives termination except for breaches disclosed on Schedule 4.2.
IP indemnity is capped at twelve months of fees paid in the prior contract year.

# Carve-outs

Gross negligence, willful misconduct, and violations of export control law are excluded
from the liability cap. Privacy fines under state consumer laws remain subject to a
separate sub-cap of five hundred thousand dollars.

# Sterling Vale drafting

Use the clause bank in Knowledge & Precedents. Cross-link data processing addenda when
the vendor hosts health information subject to HIPAA business associate terms.
""".strip(),
        "questions": [
            {
                "q": "What is the separate sub-cap for privacy fines under state consumer laws?",
                "a": "Five hundred thousand dollars is the separate sub-cap for those privacy fines.",
            },
        ],
    },
    {
        "workspace": "Knowledge & Precedents",
        "filename": "Clause_Bank_Confidentiality_2025.pdf",
        "title": "Clause Bank - Confidentiality (2025 refresh)",
        "body": """
# Mutual confidentiality

Each party may disclose confidential information to affiliates and professional advisers
bound by confidentiality obligations no less protective than this agreement.

# Residuals

The receiving party may use residuals of confidential information retained in unaided memory
without breach, except where trade secrets are clearly identified in Exhibit A.

# Maintenance

Review this clause bank quarterly. Tag superseded language with DEPRECATED and migrate
active deals to template version KB-CONF-2025-03.
""".strip(),
        "questions": [
            {
                "q": "Who may receive confidential information under the mutual confidentiality section?",
                "a": "Affiliates and professional advisers bound by confidentiality obligations at least as protective as the agreement.",
            },
        ],
    },
    {
        "workspace": "Client Intake & Conflicts",
        "filename": "Conflict_Check_Workflow.pdf",
        "title": "Conflict Check Workflow - New Business",
        "body": """
# Intake steps

Collect entity legal name, fictitious names, and top five adverse parties from the last
five years. Run the conflicts database search across matters and archived closed files.

# Wall and screening

If a positional conflict is identified, route to the ethics partner before any substantive
work. Document the wall memo in the Client Intake workspace within two business days.

# Engagement letter

Do not begin billable work until the engagement letter is countersigned and the retainer
clears according to the billing policy in General.
""".strip(),
        "questions": [
            {
                "q": "How soon must we document the wall memo in the Client Intake workspace?",
                "a": "Within two business days.",
            },
        ],
    },
]


def write_demo_pdf(*, dest: Path, doc_title: str, body: str) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, doc_title)
    pdf.ln(3)
    pdf.set_font("Helvetica", size=10)
    for line in body.strip().splitlines():
        line = line.strip()
        if not line:
            pdf.ln(2)
            continue
        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(0, 6, line[2:].strip())
            pdf.ln(1)
            pdf.set_font("Helvetica", size=10)
        else:
            pdf.multi_cell(0, 5, line)
            pdf.ln(1)
    pdf.output(str(dest))
