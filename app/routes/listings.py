"""
/listings endpoints — public read-only for buyers.

For now:
    GET /listings             — list listings with optional filters
    GET /listings/{id}        — single listing detail
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import get_db


router = APIRouter(prefix="/listings", tags=["listings"])


# ----------------------------------------------------------------
# Response models — what the API returns. Pydantic enforces shape.
# ----------------------------------------------------------------

class ListingSummary(BaseModel):
    """A lightweight listing shape for list views (search results, home page)."""
    id: UUID
    title: str
    subtitle: Optional[str] = None
    locality: str
    city: str
    price: int
    price_label: str = Field(description="Formatted for display, e.g. '4.25 Cr'")
    bhk: int
    baths: int
    area_sqft: int
    property_type: str
    possession: Optional[str] = None
    illustration: Optional[str] = None
    color: Optional[str] = None
    verified: bool
    featured: bool


class ListingDetail(ListingSummary):
    """Full listing shape for the detail page — adds description, amenities, etc."""
    description: Optional[str] = None
    builder: Optional[str] = None
    age_years: Optional[str] = None
    amenities: list[str]
    lat: Optional[float] = None
    lng: Optional[float] = None


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def _format_price_label(price: int) -> str:
    """Convert rupees to a display string. 42500000 -> '4.25 Cr', 9500000 -> '95 L'."""
    if price >= 10_000_000:
        crores = price / 10_000_000
        return f"{crores:.2f}".rstrip("0").rstrip(".") + " Cr"
    if price >= 100_000:
        lakhs = price / 100_000
        return f"{lakhs:.2f}".rstrip("0").rstrip(".") + " L"
    return str(price)


def _row_to_summary(row) -> ListingSummary:
    return ListingSummary(
        id=row["id"],
        title=row["title"],
        subtitle=row["subtitle"],
        locality=row["locality"],
        city=row["city"],
        price=row["price"],
        price_label=_format_price_label(row["price"]),
        bhk=row["bhk"],
        baths=row["baths"],
        area_sqft=row["area_sqft"],
        property_type=row["property_type"],
        possession=row["possession"],
        illustration=row["illustration"],
        color=row["color"],
        verified=row["verified"],
        featured=row["featured"],
    )


def _row_to_detail(row) -> ListingDetail:
    summary = _row_to_summary(row)
    return ListingDetail(
        **summary.model_dump(),
        description=row["description"],
        builder=row["builder"],
        age_years=row["age_years"],
        amenities=list(row["amenities"]) if row["amenities"] else [],
        lat=float(row["lat"]) if row["lat"] is not None else None,
        lng=float(row["lng"]) if row["lng"] is not None else None,
    )


# ----------------------------------------------------------------
# GET /listings — list with filters
# ----------------------------------------------------------------

@router.get("", response_model=list[ListingSummary])
async def list_listings(
    city: Optional[str] = Query(None, description="Filter by city, e.g. 'Mumbai'"),
    locality: Optional[str] = Query(None, description="Free-text locality match"),
    bhk: Optional[int] = Query(None, ge=1, le=10, description="Number of bedrooms"),
    property_type: Optional[str] = Query(None, description="Apartment, Villa, or Plot"),
    min_price: Optional[int] = Query(None, ge=0),
    max_price: Optional[int] = Query(None, ge=0),
    featured: Optional[bool] = Query(None, description="Only featured/picked listings"),
    sort: str = Query("relevance", description="relevance | price_asc | price_desc | area_desc"),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
):
    """Return a filtered list of active listings."""

    # Build query dynamically based on which filters were provided.
    # Using parameterised queries ($1, $2...) — never string concatenation — to prevent SQL injection.
    conditions = ["status = 'active'"]
    params: list = []

    if city:
        params.append(city)
        conditions.append(f"city = ${len(params)}")
    if locality:
        params.append(f"%{locality}%")
        conditions.append(f"locality ILIKE ${len(params)}")
    if bhk is not None:
        params.append(bhk)
        conditions.append(f"bhk = ${len(params)}")
    if property_type:
        params.append(property_type)
        conditions.append(f"property_type = ${len(params)}")
    if min_price is not None:
        params.append(min_price)
        conditions.append(f"price >= ${len(params)}")
    if max_price is not None:
        params.append(max_price)
        conditions.append(f"price <= ${len(params)}")
    if featured is not None:
        params.append(featured)
        conditions.append(f"featured = ${len(params)}")

    where_clause = " AND ".join(conditions)

    sort_clause = {
        "relevance":  "featured DESC, created_at DESC",
        "price_asc":  "price ASC",
        "price_desc": "price DESC",
        "area_desc":  "area_sqft DESC",
    }.get(sort, "featured DESC, created_at DESC")

    params.append(limit)
    query = f"""
        SELECT * FROM listings
        WHERE {where_clause}
        ORDER BY {sort_clause}
        LIMIT ${len(params)}
    """

    async with db.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [_row_to_summary(r) for r in rows]


# ----------------------------------------------------------------
# GET /listings/{id} — single listing
# ----------------------------------------------------------------

@router.get("/{listing_id}", response_model=ListingDetail)
async def get_listing(listing_id: UUID, db=Depends(get_db)):
    """Return one listing by ID."""
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM listings WHERE id = $1 AND status = 'active'",
            listing_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _row_to_detail(row)