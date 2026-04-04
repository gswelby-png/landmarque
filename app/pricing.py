from datetime import date
from sqlalchemy.orm import Session
from .models import CarPark, PricingRule, DayType


def get_day_type(d: date) -> DayType:
    # weekday = Mon-Fri, weekend = Sat-Sun
    if d.weekday() < 5:
        return DayType.weekday
    return DayType.weekend


def get_active_rule(db: Session, car_park_id: int, for_date: date) -> PricingRule | None:
    day_type = get_day_type(for_date)
    return (
        db.query(PricingRule)
        .filter(
            PricingRule.car_park_id == car_park_id,
            PricingRule.day_type == day_type,
            PricingRule.valid_from <= for_date,
            (PricingRule.valid_to == None) | (PricingRule.valid_to >= for_date),
        )
        .order_by(PricingRule.valid_from.desc())
        .first()
    )


def calculate_price(rule: PricingRule, duration_hours: int | None, is_all_day: bool) -> int:
    """Returns price in pence."""
    if is_all_day:
        if rule.all_day_pence is not None:
            return rule.all_day_pence
        # Fall back: hourly × max hours
        hours = rule.max_hourly_hours or 8
        return rule.hourly_rate_pence * hours

    if duration_hours is None:
        raise ValueError("Must specify duration or all-day")

    hourly_total = rule.hourly_rate_pence * duration_hours
    if rule.max_hourly_hours and duration_hours >= rule.max_hourly_hours:
        # Cap at max hourly charge
        capped = rule.hourly_rate_pence * rule.max_hourly_hours
        # If all-day is cheaper (or same), use all-day rate
        if rule.all_day_pence and rule.all_day_pence <= capped:
            return rule.all_day_pence
        return capped

    return hourly_total


def build_duration_options(rule: PricingRule) -> list[dict]:
    """Build the list of duration choices shown to the driver."""
    options = []
    max_h = rule.max_hourly_hours or 8
    for h in range(1, max_h + 1):
        price = calculate_price(rule, h, False)
        if rule.all_day_pence and price >= rule.all_day_pence:
            break
        options.append({
            "label": f"{h} hour{'s' if h > 1 else ''}",
            "value": str(h),
            "price_pence": price,
            "price_display": f"£{price / 100:.2f}",
        })
    if rule.all_day_pence:
        options.append({
            "label": "All day",
            "value": "all_day",
            "price_pence": rule.all_day_pence,
            "price_display": f"£{rule.all_day_pence / 100:.2f}",
        })
    return options
