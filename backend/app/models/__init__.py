"""Import the model modules for their side effect of registering tables.

Do not import this package from enums-only consumers; import
app.models.enums directly so unit tests stay driver-free.
"""

from app.models.complaint import Complaint
from app.models.prediction import Prediction
from app.models.user import User

__all__ = ["Complaint", "Prediction", "User"]
