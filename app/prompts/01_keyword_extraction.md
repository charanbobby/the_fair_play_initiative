Extract all meaningful, simplified keywords and specific terms from the provided policy document, explicitly mapping each to the related tables, fields, or business logic elements as defined in the SQL schema below. Instead of extracting verbatim full sentences, produce concise phrases or terms that best represent the key concept or rule from the policy in a way that is most helpful for mapping or business understanding (e.g., "Late arrivals (11+ mins)" instead of "Arriving 11 minutes or more after the scheduled start time"). Do not paraphrase into completely new concepts, but distill complex, lengthy policy statements down to their essential, actionable meaning for each linkage.

Your extraction remit includes, but is not limited to:
- Entities (e.g., organization, region, policy, employee)
- Field names (e.g., effective_date, points, violation, status)
- Conditions (e.g., late, absence, excused)
- Process-related terms (e.g., rule, penalty, override, trend, compliant)

# Extraction Process

1. Carefully read the entire policy document, identifying each reference to schema concepts, business logic, roles, violations, penalties, or compliance mechanisms.
2. For each relevant policy statement or rule, extract a concise, simplified keyword or phrase that best communicates the core idea, condition, or business rule—prefer short descriptors over copying full sentences.
3. Directly map each simplified term or phrase to the corresponding table(s), field(s), or business logic elements as specified in the schema.
4. Eliminate duplicated, vague, or unsupported terms.
5. Group your extracted, concise keywords to show clear linkage: for each table, field, or business logic element from the schema, list the related simplified terms/phrases found in the policy.
6. Only after a careful, step-by-step reasoning process, present your final, structured output.

Continue recursively until every potential policy keyword/phrase and its linkage is considered and simplified appropriately.

# Output Format

Return results as a JSON object structured by schema element (tables/fields/business logic). Each key should be a schema table name, field name, or business logic concept, with its value being an array of helpful, concise terms/phrases that capture policy intent and map to it. Terms not directly mappable to a specific schema element may go under an "other_relevant_terms" key.

Use clear, minimal terms or policy phrases that best summarize the relevant requirement or rule; do not copy entire sentences unless absolutely necessary to preserve unique, actionable meaning.

Example:
{
  "policy": ["policy", "effective date", "attendance policy"],
  "violation": ["tardy", "unexcused absence", "late arrival (1-10 mins)", "late arrival (11+ mins)", "early departure (11+ mins)"],
  "penalty": ["warning", "suspension", "termination"],
  "override": ["manual override"],
  "trend": ["trend analysis"],
  "employee": ["employee", "covered employee", "employee status"],
  "other_relevant_terms": ["points system", "absence documentation"]
}

(Note: Real examples should be as concise as possible while retaining all relevant detail and precisely mapping to schema/policy logic, using phrase formats such as "late arrival (11+ mins)" or "early departure (11+ mins)" instead of copying policy sentences.)

# Important

- Extract concise, meaningful keywords or phrases that most helpfully and accurately summarize the relevant policy linkage—avoid extracting full sentences unless strictly necessary.
- Never generate, invent, or speculate about keywords or schema connections beyond what is present in the policy text.
- Do not interpret beyond simplification; distill only what is present and necessary for direct mapping.
- Adhere to the structured JSON output format.

# Confidence Scoring

Set confidence_score between 0.0 and 1.0. Start at 1.0 and deduct:
  - −0.10 if the document appears truncated or incomplete
  - −0.05 per schema table where you found zero keywords (excluding point_history and alert, which are often absent)
  - −0.05 per rule/violation type where the exact point value is unclear
  - −0.05 if the document language is ambiguous about which violations are excused vs unexcused
  - −0.10 if key fields (organization name, policy name, effective date) are missing from the document
A confidence_score of 1.0 means every schema table has explicit, unambiguous coverage with zero gaps — this is extremely rare. Typical range for real policies: 0.70–0.90. NEVER return 1.0 unless the document is a perfect, unambiguous specification.

# Objective Reminder

Your goal is to exhaustively extract and map all keywords relevant for the SQL schema, using the most helpful, minimal phrases possible, ensuring zero hallucination and factual completeness. Think step by step, referencing the schema for alignment, and present only the final, structured JSON object after your reasoning and mapping process is complete.
