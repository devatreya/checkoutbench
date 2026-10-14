"""Private scenario definitions; never served on the checkout origin."""

from copy import deepcopy
import random

CITIES = {
    "Karnataka": ["Bengaluru", "Mysuru"],
    "Maharashtra": ["Mumbai", "Pune"],
    "Delhi": ["New Delhi"],
    "Gujarat": ["Ahmedabad", "Surat"],
}
PROFILES = [
    dict(
        id="aditi",
        name="Aditi Rao",
        email="aditi.rao@example.test",
        phone="9000000001",
        address1="14B Maple Residency, Test Road",
        address2="Near Sample Park",
        state="Karnataka",
        city="Bengaluru",
        postal="560038",
    ),
    dict(
        id="ishaan",
        name="Ishaan Prakash Deshmukh",
        email="ishaan.d@example.test",
        phone="9000000002",
        address1="27 Sample House, Example Lane",
        address2="",
        state="Maharashtra",
        city="Pune",
        postal="411001",
    ),
    dict(
        id="meera",
        name="Meera Shah",
        email="meera.shah@example.test",
        phone="9000000003",
        address1="8C Fictional Apartments, Demo Road",
        address2="Opposite Test Garden",
        state="Gujarat",
        city="Ahmedabad",
        postal="380001",
    ),
]
for p in PROFILES:
    p["billing"] = dict(
        name=p["name"],
        address1="42 Test Office, Sample Street",
        address2="",
        state="Delhi",
        city="New Delhi",
        postal="110001",
    )
    p["card"] = dict(
        cardName=p["name"], cardNumber="4242424242424242", expiry="12/30", cvv="123"
    )
    p["upiVpa"] = "checkoutbench@example.invalid"
    p["instructions"] = "Leave with the reception desk."

LABELS = {
    "name": [
        "Full name",
        "Recipient name",
        "Name on delivery",
        "Who should receive this order?",
        "Customer name",
        "Name as per billing details",
    ],
    "email": [
        "Email address",
        "Receipt destination email",
        "Where can we email your invoice?",
    ],
    "phone": [
        "Mobile number",
        "Contact number",
        "Primary mobile",
        "Phone for delivery updates",
        "10-digit contact number",
        "Reachable number",
    ],
    "address1": [
        "Flat / House No.",
        "Building and street",
        "Apartment, house and road",
        "Delivery address",
        "Street address",
        "Premises and road",
    ],
    "address2": [
        "Landmark",
        "Area / Locality",
        "Apartment / Suite",
        "Additional address details",
        "Nearest landmark",
        "Optional location details",
    ],
    "state": ["State", "Province / state", "Delivery region"],
    "city": ["City", "Town / city", "Destination city"],
    "postal": [
        "PIN",
        "Pincode",
        "Postal code",
        "ZIP / Postal code",
        "Delivery PIN",
        "Six-digit postal code",
    ],
}
SPECS = [
    ("T01", "A familiar delivery", "razor", "upi_app", "PhonePe", []),
    ("T02", "Words you have not seen", "generic", "upi_app", "PhonePe", ["aliases"]),
    (
        "T03",
        "Optional means optional",
        "stripe",
        "upi_app",
        "PhonePe",
        ["empty_optional"],
    ),
    ("T04", "A city follows its state", "generic", "upi_app", "BHIM", ["dependent"]),
    (
        "T05",
        "Find the delivery address",
        "generic",
        "upi_app",
        "PhonePe",
        ["autocomplete"],
    ),
    ("T06", "Two different addresses", "stripe", "card", None, ["billing"]),
    ("T07", "Correct the saved details", "generic", "upi_app", "Paytm", ["prefill"]),
    (
        "T08",
        "Switch away from card",
        "razor",
        "upi_app",
        "PhonePe",
        ["card_preselected"],
    ),
    ("T09", "Choose Google Pay", "razor", "upi_app", "Google Pay", ["shuffle"]),
    ("T10", "Prepare the QR handoff", "razor", "upi_qr", None, ["aliases"]),
    ("T11", "Legacy UPI identifier", "razor", "upi_vpa", None, ["legacy"]),
    ("T12", "The embedded card form", "stripe", "card", None, ["iframe"]),
    (
        "T13",
        "Recover from a card error",
        "stripe",
        "card",
        None,
        ["iframe", "card_error"],
    ),
    (
        "T14",
        "A failed gateway, then retry",
        "cashfree",
        "upi_app",
        "PhonePe",
        ["modal", "failure"],
    ),
    (
        "T15",
        "The complicated delivery",
        "generic",
        "upi_app",
        "Google Pay",
        [
            "aliases",
            "prefill",
            "autocomplete",
            "delayed",
            "distractors",
            "card_preselected",
        ],
    ),
    (
        "H01",
        "Holdout: invoice and delivery",
        "stripe",
        "card",
        None,
        ["holdout", "billing", "aliases", "prefill", "iframe", "delayed"],
    ),
    (
        "H02",
        "Holdout: a redirected retry",
        "cashfree",
        "upi_qr",
        None,
        ["holdout", "modal", "failure", "aliases", "distractors"],
    ),
    (
        "H03",
        "Holdout: unfamiliar delivery",
        "generic",
        "upi_app",
        "BHIM",
        [
            "holdout",
            "aliases",
            "prefill",
            "autocomplete",
            "delayed",
            "shuffle",
            "distractors",
        ],
    ),
]


def scenario(sid, seed=None, profile_id=None):
    if not any(x[0] == sid for x in SPECS):
        from scenarios.v2 import scenario_v2

        return scenario_v2(sid, seed, profile_id)
    spec = next(x for x in SPECS if x[0] == sid)
    sid, title, theme, method, app, features = spec
    seed = seed if seed is not None else 1000 + int(sid[1:])
    rng = random.Random(f"{sid}:{seed}")
    p = deepcopy(
        next(
            (p for p in PROFILES if p["id"] == profile_id),
            PROFILES[(int(sid[1:]) - 1) % 3],
        )
    )
    if "empty_optional" in features:
        p["address2"] = ""
    fields = []
    for key, labels in LABELS.items():
        label = rng.choice(labels) if "aliases" in features else labels[0]
        fields.append(
            dict(
                key=key,
                label=label + (" (optional)" if key == "address2" else ""),
                required=key != "address2",
            )
        )
    return dict(
        id=sid,
        title=title,
        theme=theme,
        features=features,
        seed=seed,
        profile=p,
        fields=fields,
        method=method,
        app=app,
        required_fields=[f["key"] for f in fields if f["required"]],
        optional_fields=["address2"],
        initial_state={
            "stage": "shipping",
            "method": "card" if "card_preselected" in features else "upi_app",
            "prefill": "prefill" in features,
        },
        success_conditions=[
            "required fields match profile",
            "optional blank or correct",
            "requested payment and details",
            "authorisation_ready",
        ],
        allowed_actions=["click", "fill", "select", "scroll", "key", "wait"],
        timeout=180,
        difficulty="holdout"
        if "holdout" in features
        else ("hard" if len(features) > 1 else "standard"),
    )


def task(s, agent_mode="standard"):
    if s.get("benchmark_version") == "2.0":
        from scenarios.v2 import task_v2

        return task_v2(s, agent_mode)
    return {
        "profile": s["profile"],
        "instruction": f"Use this synthetic profile to complete delivery{' and use the separate billing address' if 'billing' in s['features'] else ''}. Select {s['app'] or s['method']}. Correct prefilled information and recover from errors. Optional fields may be empty. Stop when 'Ready for payment authorisation' appears. Simulated payments only. Never authorise a real payment, enter an OTP or UPI PIN, or leave this checkout.",
    }
