from .admin import router as admin
from .applications import router as applications
from .auth import router as auth
from .availability import router as availability
from .bands import router as bands
from .bookings import router as bookings
from .disputes import router as disputes
from .gigs import router as gigs
from .payments import router as payments
from .recruitment_ads import router as recruitment_ads
from .reviews import router as reviews
from .setlists import router as setlists
from .users import router as users

__all__ = [
    "admin",
    "applications",
    "auth",
    "availability",
    "bands",
    "bookings",
    "disputes",
    "gigs",
    "payments",
    "recruitment_ads",
    "reviews",
    "setlists",
    "users",
]
