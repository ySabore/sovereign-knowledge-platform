/**
 * Sample chat prompts aligned with `scripts/law_firm_demo_pdf_catalog.py` (Sterling & Vale demo PDFs).
 * Keyed by workspace `name` as returned by the API (see `scripts/seed_law_firm.py`).
 */
export const DEMO_WORKSPACE_CHAT_SUGGESTIONS: Record<string, readonly string[]> = {
  General: [
    "What is the purpose of the General workspace?",
    "When may billable work begin according to the billing policy?",
  ],
  "Litigation & Disputes": [
    "What statute do we cite for federal subject-matter jurisdiction in the MTD playbook?",
    "How many days after opposition do we calendar the reply brief?",
  ],
  "Corporate & Transactions": [
    "What is the separate sub-cap for privacy fines under state consumer laws?",
  ],
  "Knowledge & Precedents": [
    "Who may receive confidential information under the mutual confidentiality section?",
  ],
  "Client Intake & Conflicts": [
    "How soon must we document the wall memo in the Client Intake workspace?",
  ],
};

/** Fallback when the workspace has no demo entry. */
export const DEFAULT_CHAT_SUGGESTIONS: readonly string[] = [
  "What are the key obligations in our policies?",
  "Summarize refund and cancellation rules.",
  "Which documents mention security or data retention?",
  "What are the deadlines or SLA terms?",
];
