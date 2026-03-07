Extract all meaningful, simplified keywords and specific terms from the provided policy document, explicitly mapping each to the related tables, fields, or business logic elements as defined in the SQL schema below. Instead of extracting verbatim full sentences, produce concise phrases or terms that best represent the key concept or rule from the policy in a way that is most helpful for mapping or business understanding (e.g., "Late arrivals (11+ mins)" instead of "Arriving 11 minutes or more after the scheduled start time"). Do not paraphrase into completely new concepts, but distill complex, lengthy policy statements down to their essential, actionable meaning for each linkage.

Your extraction remit includes, but is not limited to:
- Entities (e.g., organization, region, policy, employee)
- Field names (e.g., effective_date, points, violation, status)
- Conditions (e.g., late, absence, excused)
- Process-related terms (e.g., rule, penalty, override, trend, compliant)

CRITICAL — extract these metadata fields explicitly (downstream steps depend on them):
- **organization:** company name, facility/site name, any internal codes or abbreviations
- **region:** country, state/province, city, plant/site location, any timezone references (shift schedules, operating hours). Do NOT include legal statutes here — FMLA, ADA, USERRA, PTO, workers comp, EU Working Time Directive, etc. are labor-law attributes that belong in the region's `labor_laws` field or as exemption rules, NOT as separate region entities.
- **policy:** policy title/name, document number/code, effective date, revision date, scope (who it covers)

MISSING METADATA HANDLING — if the document does NOT explicitly state a metadata value:
- Return an EMPTY list for that field. Do NOT invent, guess, or hallucinate values.
- Do NOT echo these instructions back as keywords (e.g., do not return "company name", "plant location", "effective date" as literal keywords — those are prompts, not data).
- Do NOT fabricate dates, organization names, or region names that are not in the source text.
- If you are unsure whether a value is present, omit it. False omission is better than hallucinated data.

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

# Objective Reminder

Your goal is to exhaustively extract and map all keywords relevant for the SQL schema, using the most helpful, minimal phrases possible, ensuring zero hallucination and factual completeness. Think step by step, referencing the schema for alignment, and present only the final, structured JSON object after your reasoning and mapping process is complete.
