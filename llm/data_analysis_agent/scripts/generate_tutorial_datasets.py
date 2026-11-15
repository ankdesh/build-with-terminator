"""
Deterministic generation of realistic tutorial datasets for WPS-AI Field Guide.
Generates:
1. docs/tutorials/data/ecommerce_margin_shift.csv (Lesson 04: Shift Attribution)
2. docs/tutorials/data/logistics_sla_delays.csv (Lesson 05: Anomaly Spotlight Slice-Finding)
3. docs/tutorials/data/incident_telemetry.csv (Lesson 06: Domino Lead-Lag Timeline)
4. docs/tutorials/data/saas_churn_pricing.csv (Lesson 07: Scenario Studio & Recipes)
"""

import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path("docs/tutorials/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(42)

def generate_ecommerce_margin_shift() -> None:
    """4,200 orders across Q1 and Q2 with a -5.5% margin drop driven by shipping and returns."""
    n_orders = 4200
    dates_q1 = pd.date_range("2026-01-01", "2026-03-31", periods=2100)
    dates_q2 = pd.date_range("2026-04-01", "2026-06-30", periods=2100)
    order_dates = list(dates_q1) + list(dates_q2)
    quarters = ["Q1"] * 2100 + ["Q2"] * 2100
    
    regions = RNG.choice(["North", "South", "East", "West"], size=n_orders, p=[0.25, 0.25, 0.25, 0.25])
    categories = RNG.choice(["Apparel", "Electronics", "Home & Living", "Beauty"], size=n_orders, p=[0.35, 0.30, 0.20, 0.15])
    
    # Base revenue and costs
    unit_prices = []
    shipping_costs = []
    refund_rates = []
    
    for i in range(n_orders):
        q = quarters[i]
        cat = categories[i]
        reg = regions[i]
        
        # Base unit price with slight Q2 Apparel price uplift (+0.6% margin effect)
        if cat == "Apparel":
            base_p = 45.0 + (3.0 if q == "Q2" else 0.0) + RNG.normal(0, 5)
        elif cat == "Electronics":
            base_p = 120.0 + RNG.normal(0, 15)
        elif cat == "Home & Living":
            base_p = 65.0 + RNG.normal(0, 8)
        else:
            base_p = 35.0 + RNG.normal(0, 4)
        base_p = max(15.0, round(base_p, 2))
        unit_prices.append(base_p)
        
        # Shipping cost: massive Q2 air freight spike on West/North (-4.4% margin effect)
        if q == "Q2" and (reg in ["North", "West"]) and cat == "Electronics":
            ship = 38.5 + RNG.normal(0, 4.0)
        elif q == "Q2" and (reg in ["North", "West"]):
            ship = 24.0 + RNG.normal(0, 3.0)
        else:
            ship = 12.5 + RNG.normal(0, 2.0)
        shipping_costs.append(max(6.0, round(ship, 2)))
        
        # Refunds: Q2 spike in Electronics returns (-1.7% margin effect)
        if q == "Q2" and cat == "Electronics":
            refund_rate = 0.18 + RNG.uniform(0, 0.05)
        elif cat == "Electronics":
            refund_rate = 0.08 + RNG.uniform(0, 0.03)
        else:
            refund_rate = 0.04 + RNG.uniform(0, 0.02)
        refund_rates.append(refund_rate)
        
    quantities = RNG.integers(1, 5, size=n_orders)
    gross_revenue = [round(unit_prices[i] * quantities[i], 2) for i in range(n_orders)]
    refund_amounts = [round(gross_revenue[i] * refund_rates[i], 2) for i in range(n_orders)]
    
    # Base COGS ~52% of gross
    cogs = [round(gross_revenue[i] * 0.52, 2) for i in range(n_orders)]
    net_profit = [round(gross_revenue[i] - cogs[i] - shipping_costs[i] - refund_amounts[i], 2) for i in range(n_orders)]
    margin_pct = [round((net_profit[i] / gross_revenue[i]) * 100, 2) for i in range(n_orders)]
    
    df = pd.DataFrame({
        "order_id": [f"ORD-{10000 + i}" for i in range(n_orders)],
        "order_date": [d.strftime("%Y-%m-%d") for d in order_dates],
        "quarter": quarters,
        "region": regions,
        "product_category": categories,
        "quantity": quantities,
        "unit_price": unit_prices,
        "gross_revenue": gross_revenue,
        "shipping_cost": shipping_costs,
        "refund_amount": refund_amounts,
        "net_profit": net_profit,
        "margin_pct": margin_pct,
    })
    
    out_path = DATA_DIR / "ecommerce_margin_shift.csv"
    df.to_csv(out_path, index=False)
    print(f"Generated {out_path}: {len(df)} rows. Q1 margin: {df[df.quarter == 'Q1'].margin_pct.mean():.1f}%, Q2 margin: {df[df.quarter == 'Q2'].margin_pct.mean():.1f}%")

def generate_logistics_sla_delays() -> None:
    """5,000 shipments with acute 3.8x delay concentration in origin_hub='North' & carrier='ExpressAir'."""
    n_shipments = 5000
    dates = pd.date_range("2026-09-01", "2026-10-31", periods=n_shipments)
    
    hubs = RNG.choice(["North", "South", "East", "West", "Central"], size=n_shipments, p=[0.24, 0.22, 0.20, 0.18, 0.16])
    carriers = RNG.choice(["ExpressAir", "GroundFlex", "SwiftCargo", "RegionalPost"], size=n_shipments, p=[0.20, 0.40, 0.25, 0.15])
    tiers = RNG.choice(["Standard", "Heavy", "Fragile", "Perishable"], size=n_shipments, p=[0.50, 0.25, 0.15, 0.10])
    
    target_sla_days = []
    transit_days = []
    delay_hours = []
    is_delayed = []
    shipping_cost = []
    
    for i in range(n_shipments):
        h = hubs[i]
        c = carriers[i]
        t = tiers[i]
        
        target = 2 if c == "ExpressAir" else (3 if c == "SwiftCargo" else 5)
        target_sla_days.append(target)
        
        # Acute problem slice: North + ExpressAir
        if h == "North" and c == "ExpressAir":
            p_delay = 0.44  # 44% delayed vs normal ~8%
            cost = 40.20 + RNG.normal(0, 4.0)
            if RNG.random() < p_delay:
                del_h = 36.0 + RNG.exponential(12.0)
                actual_days = target + int(np.ceil(del_h / 24.0))
                delayed = 1
            else:
                del_h = 0.0
                actual_days = target
                delayed = 0
        else:
            p_delay = 0.075
            cost = (22.0 if c == "ExpressAir" else 12.5) + RNG.normal(0, 2.0)
            if RNG.random() < p_delay:
                del_h = 6.0 + RNG.exponential(6.0)
                actual_days = target + int(np.ceil(del_h / 24.0))
                delayed = 1
            else:
                del_h = 0.0
                actual_days = target
                delayed = 0
                
        transit_days.append(actual_days)
        delay_hours.append(round(del_h, 1))
        is_delayed.append(delayed)
        shipping_cost.append(max(8.0, round(cost, 2)))
        
    df = pd.DataFrame({
        "shipment_id": [f"TRK-{50000 + i}" for i in range(n_shipments)],
        "dispatch_date": [d.strftime("%Y-%m-%d") for d in dates],
        "origin_hub": hubs,
        "carrier": carriers,
        "package_tier": tiers,
        "target_sla_days": target_sla_days,
        "actual_transit_days": transit_days,
        "delay_hours": delay_hours,
        "is_delayed": is_delayed,
        "shipping_cost_usd": shipping_cost,
    })
    
    out_path = DATA_DIR / "logistics_sla_delays.csv"
    df.to_csv(out_path, index=False)
    culprit = df[(df.origin_hub == "North") & (df.carrier == "ExpressAir")]
    print(f"Generated {out_path}: {len(df)} rows. Overall delay rate: {df.is_delayed.mean()*100:.1f}%, Culprit (North+Express) delay rate: {culprit.is_delayed.mean()*100:.1f}%")

def generate_incident_telemetry() -> None:
    """72 hourly snapshots showing API Gateway latency spike at T=37 cascading down to revenue drop."""
    hours = 72
    time_index = pd.date_range("2026-11-03 00:00:00", periods=hours, freq="h")
    
    api_latency = []
    checkout_errors = []
    cart_abandonment = []
    hourly_revenue = []
    support_tickets = []
    
    for t in range(hours):
        # Baseline noise
        base_lat = 42.0 + RNG.normal(0, 3.0)
        base_err = 0.20 + RNG.normal(0, 0.04)
        base_aban = 22.0 + RNG.normal(0, 1.2)
        base_rev = 18500.0 + RNG.normal(0, 400.0)
        base_tickets = 12 + RNG.integers(0, 4)
        
        # T=37: Event Pin T=0 - API Gateway Latency breaks
        if 37 <= t < 49:
            incident_severity = np.exp(-(t - 37) / 8.0)
            # 1. API Latency spikes immediately at T=37
            lat = base_lat + 750.0 * incident_severity
            # 2. Checkout errors spike with 1 hour lag (T=38)
            err = base_err + (3.6 * incident_severity if t >= 38 else 0.4)
            # 3. Cart abandonment jumps with 2 hour lag (T=39)
            aban = base_aban + (19.0 * incident_severity if t >= 39 else 2.0)
            # 4. Hourly revenue plunges with 3 hour lag (T=40)
            rev = base_rev - (4800.0 * incident_severity if t >= 40 else 800.0)
            tickets = base_tickets + int(65 * incident_severity)
        else:
            lat = base_lat
            err = max(0.05, base_err)
            aban = base_aban
            rev = base_rev
            tickets = base_tickets
            
        api_latency.append(round(lat, 1))
        checkout_errors.append(round(max(0.05, err), 2))
        cart_abandonment.append(round(aban, 1))
        hourly_revenue.append(round(rev, 2))
        support_tickets.append(int(tickets))
        
    df = pd.DataFrame({
        "timestamp": [d.strftime("%Y-%m-%d %H:%M:%S") for d in time_index],
        "hour_offset": range(hours),
        "api_gateway_latency_ms": api_latency,
        "checkout_error_rate_pct": checkout_errors,
        "cart_abandonment_pct": cart_abandonment,
        "hourly_revenue_usd": hourly_revenue,
        "support_tickets_opened": support_tickets,
    })
    
    out_path = DATA_DIR / "incident_telemetry.csv"
    df.to_csv(out_path, index=False)
    print(f"Generated {out_path}: {len(df)} snapshots. Peak latency: {df.api_gateway_latency_ms.max()}ms at hour {df.api_gateway_latency_ms.idxmax()}")

def generate_saas_churn_pricing() -> None:
    """3,500 B2B SaaS subscriber accounts with levers (price, discount, support SLA) vs locks (tier, industry)."""
    n_accounts = 3500
    
    tiers = RNG.choice(["Starter", "Professional", "Enterprise"], size=n_accounts, p=[0.50, 0.35, 0.15])
    industries = RNG.choice(["Tech & SaaS", "Healthcare", "Fintech", "Retail & E-Com"], size=n_accounts, p=[0.40, 0.25, 0.20, 0.15])
    contract_lengths = RNG.choice([1, 12, 24, 36], size=n_accounts, p=[0.25, 0.45, 0.20, 0.10])
    
    monthly_prices = []
    discounts = []
    support_hours = []
    onboarding_calls = []
    churn_risk_scores = []
    has_churned = []
    
    for i in range(n_accounts):
        tier = tiers[i]
        ind = industries[i]
        cl = contract_lengths[i]
        
        # Levers
        if tier == "Starter":
            price = 35.0 + RNG.normal(0, 6.0)
            support = 24.0 + RNG.normal(0, 6.0)
            calls = RNG.integers(0, 2)
            disc = RNG.choice([0, 5, 10, 15], p=[0.50, 0.30, 0.15, 0.05])
        elif tier == "Professional":
            price = 75.0 + RNG.normal(0, 10.0)
            support = 12.0 + RNG.normal(0, 3.0)
            calls = RNG.integers(1, 4)
            disc = RNG.choice([0, 10, 15, 20], p=[0.40, 0.35, 0.15, 0.10])
        else: # Enterprise
            price = 150.0 + RNG.normal(0, 20.0)
            support = 4.0 + RNG.normal(0, 1.5)
            calls = RNG.integers(3, 6)
            disc = RNG.choice([10, 20, 25, 30], p=[0.20, 0.40, 0.25, 0.15])
            
        price = max(19.0, min(220.0, round(price, 2)))
        support = max(1.0, min(48.0, round(support, 1)))
        
        # Risk score calculation (ground truth response surface)
        # Churn increases with slow support SLA and high prices without discounts, reduced by onboarding calls and longer contracts
        risk = 0.08 + (support / 48.0) * 0.12 - (calls * 0.02) - (0.04 if cl >= 12 else 0.0) + (price / 200.0) * 0.05 - (disc / 100.0) * 0.06 + RNG.normal(0, 0.015)
        risk = max(0.01, min(0.40, round(risk, 3)))
        churned = 1 if RNG.random() < risk else 0
        
        monthly_prices.append(price)
        discounts.append(disc)
        support_hours.append(support)
        onboarding_calls.append(calls)
        churn_risk_scores.append(risk)
        has_churned.append(churned)
        
    df = pd.DataFrame({
        "account_id": [f"ACC-{1000 + i}" for i in range(n_accounts)],
        "subscription_tier": tiers,
        "industry": industries,
        "contract_length_months": contract_lengths,
        "monthly_seat_price": monthly_prices,
        "applied_discount_pct": discounts,
        "support_sla_response_hours": support_hours,
        "onboarding_calls_completed": onboarding_calls,
        "churn_risk_score": churn_risk_scores,
        "has_churned": has_churned,
    })
    
    out_path = DATA_DIR / "saas_churn_pricing.csv"
    df.to_csv(out_path, index=False)
    print(f"Generated {out_path}: {len(df)} accounts. Average churn rate: {df.has_churned.mean()*100:.1f}%, Average price: ${df.monthly_seat_price.mean():.2f}")

if __name__ == "__main__":
    generate_ecommerce_margin_shift()
    generate_logistics_sla_delays()
    generate_incident_telemetry()
    generate_saas_churn_pricing()
