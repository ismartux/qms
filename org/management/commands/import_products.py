import csv
import os
import sys
import django

# ==============================
# Django setup
# ==============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# ==============================
# Import models
# ==============================
from org.models import Product, Company, Plant


# ==============================
# CONFIG (LOCKED IDS)
# ==============================
COMPANY_ID = 2   # IsmartU India Private Limited
PLANT_ID = 2     # TUW1 under company 2

CSV_PATH = os.path.join(BASE_DIR, "transsflow", "data", "products.csv")


def run():
    # ------------------------------
    # Validate Company & Plant
    # ------------------------------
    try:
        company = Company.objects.get(id=COMPANY_ID)
    except Company.DoesNotExist:
        print(f"❌ Company not found with id={COMPANY_ID}")
        return

    try:
        plant = Plant.objects.get(id=PLANT_ID)
    except Plant.DoesNotExist:
        print(f"❌ Plant not found with id={PLANT_ID}")
        return

    if plant.company_id != company.id:
        print("❌ Plant does not belong to selected company")
        return

    print(f"✔ Using Company: {company.name}")
    print(f"✔ Using Plant: {plant.code} ({company.name})\n")

    # ------------------------------
    # Validate CSV
    # ------------------------------
    if not os.path.exists(CSV_PATH):
        print(f"❌ CSV file not found: {CSV_PATH}")
        return

    created = 0
    skipped = 0

    with open(CSV_PATH, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            code = row["code"].strip()

            product, is_created = Product.objects.get_or_create(
                company=company,        # 🔒 FORCE company
                plant=plant,            # 🔒 FORCE plant
                code=code,
                defaults={
                    "name": row["name"].strip(),
                    "category": row.get("category", "").strip(),
                    "position": row.get("position", "").strip(),
                    "brand": row.get("brand", "").strip(),
                },
            )

            if is_created:
                created += 1
                print(f"✅ Created: {product.code}")
            else:
                skipped += 1
                print(f"⚠️ Skipped (exists): {product.code}")

    print("\n==============================")
    print("🎉 Import finished")
    print(f"   Company: {company.name}")
    print(f"   Plant  : {plant.code}")
    print(f"   Created: {created}")
    print(f"   Skipped: {skipped}")
    print("==============================\n")


if __name__ == "__main__":
    run()
