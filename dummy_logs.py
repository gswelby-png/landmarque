"""Generate 50 dummy transactions — 12 currently active, 38 historical."""
from dotenv import load_dotenv; load_dotenv()

from datetime import datetime, timedelta, timezone
import random
from app.database import SessionLocal
from app import models

db = SessionLocal()

cp = db.query(models.CarPark).filter_by(slug='shere-manor').first()
if not cp:
    print("Car park not found"); exit()

plates = [
    "AB12CDE","XY98ZZZ","LM45NOP","QR67STU","VW23ABC",
    "EF89GHI","JK34LMN","PQ56RST","UV78WXY","CD11EFG",
    "HI22JKL","MN33OPQ","RS44TUV","WX55YZA","BC66DEF",
    "GH77IJK","LM88NOP","QR99STU","VW00XYZ","AB33CDE",
    "XY44ZZZ","LM55NOP","QR66STU","VW77ABC","EF00GHI",
    "JK11LMN","PQ22RST","UV33WXY","CD44EFG","HI55JKL",
    "MN66OPQ","RS77TUV","WX88YZA","BC99DEF","GH00IJK",
    "TF12ABX","KP34MNZ","SW56QRY","DL78CEH","OA90FGJ",
    "BN23KLV","YM45NRW","HE67PSX","UG89CIT","RJ01MBD",
    "ZQ13NAF","IC35OTG","PV57LUH","FK79EVI","AL91DWJ",
]

durations = [1, 2, 3, 4, None]  # None = all day
hourly = 300  # 3.00/hr
all_day = 1200  # 12.00

now = datetime.now(timezone.utc)

# 38 historical (past 30 days, expired)
for i in range(38):
    is_all_day = random.choice([True, False, False])
    dur = None if is_all_day else random.choice([1, 2, 3, 4])
    amount = all_day if is_all_day else hourly * dur
    commission = int(amount * cp.owner.commission_pct / 100)
    parked_at = now - timedelta(
        days=random.randint(1, 30),
        hours=random.randint(0, 10),
        minutes=random.randint(0, 59)
    )
    expires_at = None if is_all_day else parked_at + timedelta(hours=dur)

    db.add(models.Transaction(
        car_park_id=cp.id,
        number_plate=random.choice(plates),
        duration_hours=dur,
        is_all_day=is_all_day,
        amount_pence=amount,
        commission_pence=commission,
        owner_amount_pence=amount - commission,
        status=models.TransactionStatus.paid,
        parked_at=parked_at,
        expires_at=expires_at,
    ))

# 12 currently active (parked recently, expires in the future)
for i in range(12):
    dur = random.choice([1, 2, 3, 4])
    amount = hourly * dur
    commission = int(amount * cp.owner.commission_pct / 100)
    # Parked between 5 mins and 90 mins ago
    parked_at = now - timedelta(minutes=random.randint(5, 90))
    expires_at = parked_at + timedelta(hours=dur)

    db.add(models.Transaction(
        car_park_id=cp.id,
        number_plate=random.choice(plates),
        duration_hours=dur,
        is_all_day=False,
        amount_pence=amount,
        commission_pence=commission,
        owner_amount_pence=amount - commission,
        status=models.TransactionStatus.paid,
        parked_at=parked_at,
        expires_at=expires_at,
    ))

db.commit()
db.close()
print("Done: 38 historical + 12 active transactions created.")
