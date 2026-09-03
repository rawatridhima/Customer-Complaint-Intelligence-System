"""Maps CFPB source products to the six system categories (DR-02).

Version this file. Changing it invalidates every trained model.
"""

MAPPING_VERSION = "v1"

CFPB_TO_CATEGORY: dict[str, str] = {
    "Credit card or prepaid card": "billing",
    "Checking or savings account": "billing",
    "Money transfer, virtual currency, or money service": "refund",
    "Debt collection": "service_quality",
    "Mortgage": "billing",
    "Student loan": "billing",
    "Vehicle loan or lease": "billing",
    "Credit reporting, credit repair services, or other personal consumer reports":
        "technical",
    "Payday loan, title loan, or personal loan": "billing",
}

CATEGORIES = [
    "billing", "delivery", "product_defect",
    "service_quality", "technical", "refund",
]
