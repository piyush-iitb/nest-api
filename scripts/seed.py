"""
Seed script: populate the database with the 6 mock listings from the frontend.

Run from the project root with venv activated:
    python -m scripts.seed

Safe to run multiple times — it clears existing seed data first.
"""

import asyncio
import asyncpg
from app.config import settings


LISTINGS = [
    {
        "title": "Skyline Residences", "subtitle": "Tower B, 22nd Floor",
        "locality": "Bandra West", "city": "Mumbai",
        "lat": 19.0596, "lng": 72.8295,
        "price": 42500000, "bhk": 3, "baths": 3, "area_sqft": 1480,
        "property_type": "Apartment", "possession": "Ready to move",
        "builder": "Lodha Developers", "age_years": "3 years",
        "amenities": ["Sea view", "Private gym", "Infinity pool", "24/7 concierge", "Valet parking", "Smart home"],
        "description": "A rare west-facing residence in one of Bandra's most coveted addresses. "
                       "Floor-to-ceiling windows frame the Arabian Sea, and the home has been designed "
                       "with a restrained palette of oak, travertine, and brushed brass.",
        "illustration": "skyline", "color": "#E8DCC8",
        "verified": True, "featured": True,
    },
    {
        "title": "The Walden", "subtitle": "Garden Wing",
        "locality": "Powai", "city": "Mumbai",
        "lat": 19.1176, "lng": 72.9060,
        "price": 28500000, "bhk": 3, "baths": 2, "area_sqft": 1240,
        "property_type": "Apartment", "possession": "Dec 2025",
        "builder": "Hiranandani", "age_years": "Under construction",
        "amenities": ["Lake view", "Clubhouse", "Jogging track", "Co-working lounge"],
        "description": "Garden-facing apartment in a low-density development by the lake. "
                       "Quieter than the towers, with mature landscaping and a real sense of community.",
        "illustration": "walden", "color": "#D4E4D4",
        "verified": True, "featured": False,
    },
    {
        "title": "Vasant House", "subtitle": "Standalone Villa",
        "locality": "Juhu", "city": "Mumbai",
        "lat": 19.1075, "lng": 72.8263,
        "price": 67500000, "bhk": 4, "baths": 4, "area_sqft": 2100,
        "property_type": "Villa", "possession": "Ready to move",
        "builder": "Independent", "age_years": "5 years",
        "amenities": ["Private garden", "Pool", "Servant quarters", "Solar panels", "EV charging"],
        "description": "A standalone four-bedroom home set back from the road on a leafy lane. "
                       "Built in 2019 with thoughtful proportions and a small but lush garden.",
        "illustration": "vasant", "color": "#F4D4C4",
        "verified": True, "featured": True,
    },
    {
        "title": "Marine Heights", "subtitle": "18th Floor, Sea-facing",
        "locality": "Worli", "city": "Mumbai",
        "lat": 19.0096, "lng": 72.8156,
        "price": 95000000, "bhk": 4, "baths": 5, "area_sqft": 2680,
        "property_type": "Apartment", "possession": "Ready to move",
        "builder": "Oberoi Realty", "age_years": "2 years",
        "amenities": ["Panoramic sea view", "Private elevator", "Wine cellar", "Two parking bays", "Home theatre"],
        "description": "High-floor apartment with uninterrupted views across the Worli sea face. "
                       "Private elevator opens directly into the residence.",
        "illustration": "marine", "color": "#D8E0EC",
        "verified": True, "featured": True,
    },
    {
        "title": "Casa Verde", "subtitle": "Carter Road",
        "locality": "Bandra West", "city": "Mumbai",
        "lat": 19.0606, "lng": 72.8347,
        "price": 18500000, "bhk": 2, "baths": 2, "area_sqft": 920,
        "property_type": "Apartment", "possession": "Ready to move",
        "builder": "Rustomjee", "age_years": "8 years",
        "amenities": ["Balcony", "Gym", "Power backup"],
        "description": "A bright two-bedroom in a quiet by-lane off Carter Road. "
                       "Recently renovated with new fittings throughout.",
        "illustration": "casaVerde", "color": "#EDE0F0",
        "verified": True, "featured": False,
    },
    {
        "title": "The Quay", "subtitle": "Sea-facing residences",
        "locality": "Worli", "city": "Mumbai",
        "lat": 19.0144, "lng": 72.8181,
        "price": 54000000, "bhk": 3, "baths": 3, "area_sqft": 1680,
        "property_type": "Apartment", "possession": "Jun 2026",
        "builder": "K Raheja Corp", "age_years": "Under construction",
        "amenities": ["Sea view", "Infinity pool", "Spa", "Concierge"],
        "description": "Premium tower under construction with an infinity pool overlooking the sea. "
                       "Possession expected mid-2026.",
        "illustration": "quay", "color": "#E4E8D4",
        "verified": True, "featured": False,
    },
]


INSERT_SQL = """
INSERT INTO listings (
    title, subtitle, description, locality, city, lat, lng,
    price, bhk, baths, area_sqft, property_type, possession,
    builder, age_years, amenities, illustration, color,
    verified, verified_at, featured, status
) VALUES (
    $1, $2, $3, $4, $5, $6, $7,
    $8, $9, $10, $11, $12, $13,
    $14, $15, $16, $17, $18,
    $19, CASE WHEN $19 THEN NOW() ELSE NULL END, $20, 'active'
)
"""


async def seed():
    conn = await asyncpg.connect(settings.database_url)
    try:
        # Clear existing seed data (idempotent: safe to re-run)
        deleted = await conn.execute("DELETE FROM listings")
        print(f"Cleared existing listings: {deleted}")

        # Insert all 6 listings
        for listing in LISTINGS:
            await conn.execute(
                INSERT_SQL,
                listing["title"], listing["subtitle"], listing["description"],
                listing["locality"], listing["city"], listing["lat"], listing["lng"],
                listing["price"], listing["bhk"], listing["baths"], listing["area_sqft"],
                listing["property_type"], listing["possession"],
                listing["builder"], listing["age_years"], listing["amenities"],
                listing["illustration"], listing["color"],
                listing["verified"], listing["featured"],
            )
            print(f"  + {listing['title']}")

        count = await conn.fetchval("SELECT COUNT(*) FROM listings")
        print(f"\nSeeded {count} listings successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())