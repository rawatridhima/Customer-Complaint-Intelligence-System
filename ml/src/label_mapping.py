"""Maps CFPB Product + Issue to the six system categories (DR-02).

Version this file. Changing it invalidates every trained model.
"""

MAPPING_VERSION = "v2"

CATEGORIES = [
    "credit_report_dispute", "report_misuse", "debt_collection",
    "cards_and_accounts", "mortgage", "consumer_loans",
]

CREDIT_REPORTING = (
    "Credit reporting, credit repair services, or other personal consumer reports"
)

PRODUCT_TO_CATEGORY: dict[str, str] = {
    "Debt collection": "debt_collection",
    "Credit card or prepaid card": "cards_and_accounts",
    "Checking or savings account": "cards_and_accounts",
    "Money transfer, virtual currency, or money service": "cards_and_accounts",
    "Mortgage": "mortgage",
    "Student loan": "consumer_loans",
    "Vehicle loan or lease": "consumer_loans",
    "Payday loan, title loan, or personal loan": "consumer_loans",
}


def map_label(product: str, issue: str) -> str | None:
    """Return the system category, or None if the row should be dropped."""
    if product == CREDIT_REPORTING:
        if issue == "Improper use of your report":
            return "report_misuse"
        return "credit_report_dispute"
    return PRODUCT_TO_CATEGORY.get(product)