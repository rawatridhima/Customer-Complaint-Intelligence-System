"""Sample knowledge base: internal support procedures, two per category.

These are the documents suggested resolutions are grounded in (FR-20). They
describe the procedures of the fictional company the system is demonstrated
for; they are not legal advice. Replace them with a real organisation's
articles, or add more through POST /api/v1/knowledge-articles (managers).
"""

from app.models.enums import Category

KNOWLEDGE_ARTICLES: list[tuple[Category, str, str]] = [
    # ---- credit_report_dispute ----------------------------------------------
    (
        Category.CREDIT_REPORT_DISPUTE,
        "Handling a dispute about inaccurate credit report information",
        "1. Identify exactly which item the customer says is wrong: account, balance, "
        "payment status, dates, or an account they do not recognise.\n"
        "2. Check our own records for that account. If our reporting is wrong, raise a "
        "correction with the Credit Reporting team the same day and tell the customer.\n"
        "3. If our records match what was reported, explain what we reported and why, and "
        "offer to open a formal dispute review.\n"
        "4. A formal dispute review is completed within 30 days. Tell the customer the "
        "date they will hear back by.\n"
        "5. Record the dispute reference number on the case so later contacts can find it.",
    ),
    (
        Category.CREDIT_REPORT_DISPUTE,
        "When a previous dispute was not resolved",
        "If the customer says they already disputed an item and it is still reported:\n"
        "1. Find the earlier dispute reference and its outcome.\n"
        "2. If the earlier review found in the customer's favour but the item remains, "
        "escalate to the Credit Reporting team lead as a failed correction.\n"
        "3. If the earlier review upheld the item, explain the finding and ask whether the "
        "customer has new documents; new evidence opens a fresh review.\n"
        "4. Repeat disputes are marked for supervisor review before closing.",
    ),
    # ---- report_misuse -------------------------------------------------------
    (
        Category.REPORT_MISUSE,
        "Unauthorised credit inquiry or suspected identity theft",
        "Treat as urgent. 1. Do not ask the customer to repeat full identity details by "
        "email; verify identity through the secure channel only.\n"
        "2. Check whether the inquiry or account was opened through us. If so, freeze the "
        "application or account immediately and refer it to the Fraud team.\n"
        "3. Advise the customer they can place a fraud alert or security freeze with the "
        "credit bureaus, and give them our fraud case reference.\n"
        "4. The Fraud team contacts the customer within one business day.\n"
        "5. Never close the case until the Fraud team confirms the outcome.",
    ),
    (
        Category.REPORT_MISUSE,
        "Customer did not authorise a credit check",
        "1. Confirm the date and name on the inquiry.\n"
        "2. Search for any application, pre-approval or account review in that name on "
        "that date.\n"
        "3. If no permitted purpose is found, request removal of the inquiry through the "
        "Credit Reporting team and confirm in writing once done.\n"
        "4. If a permitted purpose exists (for example an existing account review), explain "
        "it plainly.\n"
        "5. Any sign of an application the customer did not make goes to the Fraud team.",
    ),
    # ---- debt_collection -----------------------------------------------------
    (
        Category.DEBT_COLLECTION,
        "Customer disputes owing a debt in collection",
        "1. Pause collection activity on the account while the dispute is reviewed.\n"
        "2. Send the customer a debt validation pack: original creditor, amount, and how "
        "the balance was calculated.\n"
        "3. If the customer says the debt is not theirs, check for identity theft and follow "
        "the fraud procedure.\n"
        "4. If the debt was already paid or settled, ask for proof of payment and check "
        "our payment records.\n"
        "5. Collection resumes only after the validation pack is sent and the dispute is "
        "reviewed.",
    ),
    (
        Category.DEBT_COLLECTION,
        "Complaints about collector conduct or contact frequency",
        "1. Apologise and record exactly what was said and when.\n"
        "2. Check contact logs for call times and frequency. Calls before 8am or after "
        "9pm local time, or repeated same-day calls, are breaches of our policy.\n"
        "3. Apply the customer's contact preferences immediately (for example written "
        "contact only).\n"
        "4. Refer any threat, abusive language or discussion of the debt with third parties "
        "to Compliance for review.\n"
        "5. Tell the customer what was changed and that Compliance may contact them.",
    ),
    # ---- cards_and_accounts --------------------------------------------------
    (
        Category.CARDS_AND_ACCOUNTS,
        "Unrecognised or duplicate card transaction",
        "1. Confirm the transaction date, amount and merchant.\n"
        "2. If the customer does not recognise it, block the card and issue a replacement.\n"
        "3. Open a transaction dispute. A provisional credit may be applied while it is "
        "investigated, following the card dispute policy.\n"
        "4. For a duplicate charge, check whether both transactions settled or one is a "
        "pending authorisation that will drop off.\n"
        "5. Disputes are resolved within 45 days; give the customer the reference number.",
    ),
    (
        Category.CARDS_AND_ACCOUNTS,
        "Fees, closures and access problems on deposit accounts",
        "1. For a disputed fee, check whether it matches the account's fee schedule and "
        "the customer's history. A first-time overdraft or late fee may be refunded once "
        "per 12 months at the agent's discretion.\n"
        "2. For a closed or frozen account, check the internal reason code. Explain what "
        "the customer can be told and how to get remaining funds.\n"
        "3. For transfers that have not arrived, trace the payment with the Payments team "
        "and give an expected date.\n"
        "4. Escalate any account the customer cannot access for more than 3 business days.",
    ),
    # ---- mortgage ------------------------------------------------------------
    (
        Category.MORTGAGE,
        "Mortgage payment, escrow or servicing errors",
        "1. Identify the error: misapplied payment, escrow shortage or overage, incorrect "
        "late fee, or wrong balance.\n"
        "2. Treat the complaint as a notice of error and acknowledge it in writing within "
        "5 business days.\n"
        "3. Pull the payment history and escrow analysis and check them against the "
        "customer's statements.\n"
        "4. Correct confirmed errors, reverse any resulting fees, and send a corrected "
        "statement.\n"
        "5. Complete the investigation within 30 business days and tell the customer the "
        "outcome in writing.",
    ),
    (
        Category.MORTGAGE,
        "Customer at risk of foreclosure or unable to pay",
        "Treat as urgent. 1. Check whether a foreclosure sale date is set; if so, escalate "
        "to the Loss Mitigation team the same day.\n"
        "2. Explain the assistance options: forbearance, repayment plan, or loan "
        "modification review.\n"
        "3. Send the loss mitigation application and a list of the documents needed.\n"
        "4. Assign a single point of contact from Loss Mitigation and give the customer "
        "their name.\n"
        "5. Do not advise on legal matters; suggest a HUD-approved housing counsellor for "
        "independent help.",
    ),
    # ---- consumer_loans ------------------------------------------------------
    (
        Category.CONSUMER_LOANS,
        "Loan terms, interest or payments differ from what was agreed",
        "1. Pull the signed loan agreement and compare it with what the customer describes.\n"
        "2. If the terms applied differ from the signed agreement, correct the account, "
        "refund overcharged interest or fees, and confirm in writing.\n"
        "3. If the customer disputes what they were told before signing, record the details "
        "and refer to Compliance for a sales practice review.\n"
        "4. For a loan transferred to a new servicer, confirm the transfer date and that "
        "the terms carried over unchanged.",
    ),
    (
        Category.CONSUMER_LOANS,
        "Vehicle loan, repossession and student loan servicing",
        "1. Vehicle loans: before any repossession, check the account for payment plans "
        "or hardship arrangements. If a repossession happened, explain how to recover "
        "personal property and the redemption amount.\n"
        "2. Student loans: check repayment plan enrolment and whether any payments were "
        "misapplied between loans.\n"
        "3. For hardship, offer the hardship review and the documents needed.\n"
        "4. Escalate any repossession the customer says happened while a payment "
        "arrangement was active.",
    ),
]
