"""
app/sample_policies.py
----------------------
Embedded sample attendance policy texts for the Playground.
Users can load these into the policy analyzer to test the extraction
and planning pipeline without needing their own PDF/DOCX files.
"""

SAMPLE_POLICIES = [
    {
        "id": "sample-manufacturing",
        "name": "Acme Manufacturing",
        "description": "Manufacturing plant attendance policy with point-based discipline",
        "text": """ACME MANUFACTURING CO.
EMPLOYEE ATTENDANCE & PUNCTUALITY POLICY
Policy Number: HR-ATT-001 | Effective: January 1, 2024 | Region: US-West

1. PURPOSE
This policy establishes uniform standards for attendance and punctuality across all Acme Manufacturing facilities operating under California Labor Code requirements.

2. SCOPE
Applies to all full-time and part-time hourly employees in the US-West region assigned to TechCorp Industries manufacturing operations.

3. DEFINITIONS
- Tardiness: Arriving more than 7 minutes after scheduled start time.
- Early Departure: Leaving more than 15 minutes before scheduled end time without supervisor approval.
- Unexcused Absence: Missing a scheduled shift without prior approval or qualifying emergency.
- No-Call/No-Show (NCNS): Failing to report an absence AND failing to notify a supervisor within 1 hour of shift start.

4. POINT SYSTEM
Infractions accrue points on a rolling 12-month basis:
  - Tardiness (>7 min): 0.5 points
  - Early Departure (>15 min): 0.5 points
  - Unexcused Absence: 2.0 points
  - No-Call/No-Show: 3.0 points

5. DISCIPLINARY THRESHOLDS
  - 4 points: Verbal warning
  - 6 points: Written warning
  - 8 points: Final written warning / performance review
  - 10 points: Termination recommendation

6. POINT REDUCTION
Employees with 90 consecutive calendar days of perfect attendance receive a 1.0 point reduction.

7. APPROVED LEAVE EXEMPTIONS
The following do not accrue points: FMLA leave, jury duty, bereavement (up to 5 days), approved vacation, and pre-approved medical appointments with 48-hour notice.

8. RESET PERIOD
All points reset to zero after 12 months of continuous employment from the date of the oldest active infraction.""",
    },
    {
        "id": "sample-healthcare",
        "name": "NorthBridge Health Authority",
        "description": "Healthcare facility attendance policy with complex shift and overtime rules",
        "text": """NORTHBRIDGE HEALTH AUTHORITY
ATTENDANCE & RELIABILITY MANAGEMENT POLICY
Policy ID: ABS-MGMT-07 | Effective: March 15, 2024 | Region: EU-Central

1. POLICY STATEMENT
NorthBridge Health Authority (Global Solutions Ltd) is committed to maintaining reliable staffing levels in all EU-Central healthcare facilities in compliance with the EU Working Time Directive.

2. APPLICABILITY
All clinical and non-clinical staff assigned to the EU-Central region, governed by Global Solutions EU Policy.

3. ATTENDANCE EXPECTATIONS
Standard shifts: 08:00–16:00 or 20:00–04:00 (night rotation).
A 5-minute grace period applies. Tardiness is recorded after 7 minutes past scheduled start.

4. INFRACTION CATEGORIES AND POINTS
  a) Tardiness (arrival >7 min late): 0.25 points (EU multiplier 0.5x applied)
  b) Early departure (>15 min before shift end): 0.25 points
  c) Unexcused absence (full shift missed): 1.0 point
  d) No-Call/No-Show: 1.5 points
  e) Pattern absence (3+ absences on same weekday within 60 days): additional 0.5 points

5. PROGRESSIVE DISCIPLINE
  - 3 points: Verbal counseling with union representative present
  - 5 points: Written warning filed with HR
  - 8 points: Mandatory attendance improvement plan (60-day review)
  - 10 points: Suspension pending termination review

6. EXEMPTIONS (NO POINTS ASSESSED)
Pre-approved annual leave, statutory sick pay (with medical certificate), maternity/paternity leave under EU Directive 2019/1158, mandatory training days, public health emergencies declared by facility administration.

7. SHIFT SWAP PROTOCOL
Employees may swap shifts with qualified colleagues via the scheduling portal. Swaps approved by charge nurse do not count as absences.

8. OVERTIME ATTENDANCE
Voluntary overtime shifts follow standard attendance rules. Failure to appear for a confirmed overtime shift incurs 1.0 point (treated as unexcused absence).

9. REVIEW CYCLE
Points are reviewed quarterly. Employees with zero infractions for 90 days receive 0.5 point credit.""",
    },
    {
        "id": "sample-retail",
        "name": "Horizon Retail Group",
        "description": "Retail attendance policy with seasonal adjustments and weekend multipliers",
        "text": """HORIZON RETAIL GROUP
ATTENDANCE POLICY — HR-302-B
Effective: February 1, 2024 | Region: Asia Pacific | Organization: Enterprise Holdings

1. OVERVIEW
Enterprise Holdings (APAC division) operates under the Horizon Retail Group attendance framework. This policy governs attendance for all store associates, warehouse staff, and district managers in the Asia Pacific region under local Employment Acts.

2. STANDARD SCHEDULE
Store associates: rotating schedules posted 14 days in advance.
Warehouse staff: fixed shifts (06:00–14:00 or 14:00–22:00).

3. POINT ACCUMULATION
  - Late arrival (>7 min after scheduled start): 0.5 points
  - Early departure (>15 min before scheduled end): 0.5 points
  - Unexcused full-day absence: 2.0 points
  - No-Call/No-Show: 3.0 points
  - Weekend/holiday NCNS (Nov 15 – Jan 5 peak season): 4.5 points (1.5x multiplier)

4. SEASONAL BLACKOUT PERIODS
During peak retail season (November 15 through January 5), all time-off requests require district manager approval 30 days in advance. Unapproved absences during blackout periods receive a 1.5x point multiplier.

5. DISCIPLINE LADDER
  - 4 points: Documented verbal coaching
  - 6 points: Written warning with 30-day improvement plan
  - 8 points: Final warning — loss of scheduling preference
  - 10 points: Separation recommendation to HR

6. POINT REDUCTIONS AND INCENTIVES
  - 60 consecutive days perfect attendance: -0.5 points
  - Employee of the Month (zero infractions + positive customer feedback): -1.0 point
  - Volunteering for 3+ uncovered shifts in a calendar month: -0.5 points

7. EXCUSED ABSENCES (NO POINTS)
Approved personal leave, documented medical emergencies, natural disaster declarations, mandatory military service, and bereavement leave (up to 3 days for immediate family).

8. ATTENDANCE TRACKING
All clock-in/clock-out events are recorded via the HRIS biometric system. Discrepancies must be reported to the shift supervisor within 24 hours.

9. APPEALS
Employees may appeal point assessments within 7 business days through the regional HR portal. Appeals are reviewed by the district HR committee within 14 days.""",
    },
]
