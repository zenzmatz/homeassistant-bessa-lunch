"""Type definitions for Bessa Lunch integration based on official API schema."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request model for authentication."""
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class TokenResponse(BaseModel):
    """Response model for authentication token."""
    key: str = Field(..., min_length=1, max_length=40, description="Authentication token")


class OrderItem(BaseModel):
    """Model for an order item."""
    id: int
    name: str
    description: Optional[str] = None
    price: str  # Decimal as string
    amount: float
    vat: str
    article: int
    course_group: Optional[int] = None


class Order(BaseModel):
    """Model for an order."""
    id: int
    venue: int
    order_type: int  # 0-7
    order_state: int  # 1-13
    payment_method: Optional[str] = None
    date: Optional[datetime] = None
    user_date: Optional[datetime] = None
    total: str  # Decimal as string
    currency: str = Field(..., min_length=3, max_length=3)
    pickup_code: Optional[str] = None
    number: Optional[int] = None
    items: Optional[List[OrderItem]] = None
    created: datetime
    updated: datetime
    deleted: Optional[datetime] = None


class OrdersResponse(BaseModel):
    """Response model for orders list."""
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[Order]


class MenuItem(BaseModel):
    """Model for a menu item."""
    id: int
    name: str
    description: Optional[str] = None
    price: str
    allergens: Optional[str] = None
    sort: Optional[int] = None


class MenuCategory(BaseModel):
    """Model for a menu category."""
    id: int
    name: str
    description: Optional[str] = None
    items: List[MenuItem] = []
    sort: Optional[int] = None


class MenuResponse(BaseModel):
    """Response model for menu data."""
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[MenuCategory]


# Order state mapping based on official API documentation
ORDER_STATES = {
    1: "New",
    2: "Payment Processing",
    3: "Transmittable",
    4: "Transmitted",
    5: "Accepted",
    6: "Preparing",
    7: "Ready",
    8: "Done",
    9: "Cancelled",
    10: "Rejected",
    11: "Failed",
    12: "Expired",
    13: "Pre-ordered"
}


def get_order_state_name(state_code: int) -> str:
    """Get human-readable order state name."""
    return ORDER_STATES.get(state_code, "Unknown")
