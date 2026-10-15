"""Research release definitions. Old IDs/definitions are not changed.

The original shared client is ONE implementation family, regardless of branding.
New renderers and sealed candidates are inventoried separately with source hashes.
"""

from copy import deepcopy
import hashlib, json
from pathlib import Path
from scenarios.v21 import V21_SPECS, scenario_v21

RELEASE = "3.0-pilot.1"
ROOT = Path(__file__).resolve().parents[1]
TRACKS = {
    "A": "Core Checkout",
    "B": "Checkout Resilience",
    "C": "Complex / Legacy Portals",
}
IMPLEMENTATIONS = [
    ("merchant-ledger", "Purchase-order table with row validation", "development"),
    (
        "parcel-wizard",
        "Sequential address wizard with explicit client transitions",
        "development",
    ),
    ("market-dialog", "Native dialog payment interaction", "development"),
    (
        "subscription-tabs",
        "Tabbed subscription form with independent panels",
        "development",
    ),
    (
        "grocery-accordion",
        "Expandable delivery sections with validation summaries",
        "development",
    ),
    (
        "electronics-elements",
        "Custom-element checkout using open shadow DOM",
        "development",
    ),
    ("furniture-drawer", "Basket and slide-in payment drawer", "validation"),
    (
        "books-inline",
        "Inline editable address cards and review confirmation",
        "validation",
    ),
    (
        "donation-stack",
        "Stacked form fragments with a separate review step",
        "validation",
    ),
    ("travel-columns", "Two-column reservation and payment form", "validation"),
]
SPECS = [
    dict(id="V3-" + r["id"][4:], base=r["id"], design="regression") for r in V21_SPECS
]
for provider, base in [
    ("razor", "V21-RZ01"),
    ("cashfree", "V21-CF01"),
    ("generic", "V21-G01"),
]:
    for quality in range(6):
        SPECS.append(
            dict(
                id=f"V3-QR-{provider}-{quality}",
                base=base,
                design="qr",
                factor="qr_quality",
                level=f"Q{quality}",
            )
        )
for surface in ("modal", "iframe", "popup", "redirect"):
    for fault in ("valid", "otp_expired", "otp_invalid", "otp_delayed"):
        for mode in ("handoff", "simulated_completion"):
            SPECS.append(
                dict(
                    id=f"V3-AUTH-{surface}-{fault}-{mode}",
                    base="V21-ST01",
                    design="auth",
                    surface=surface,
                    fault=fault,
                    mode=mode,
                )
            )
for factor, levels in {
    "device": ["desktop", "mobile"],
    "layout": ["one-page", "three-page"],
    "labels": ["standard", "unfamiliar"],
    "density": ["modern", "dense"],
    "autofill": ["correct", "stale"],
}.items():
    for level in levels:
        SPECS.append(
            dict(
                id=f"V3-LAYOUT-{factor}-{level}",
                base="V21-S01",
                design="layout",
                factor=factor,
                level=level,
            )
        )
for impl, _, split in IMPLEMENTATIONS:
    for method in ("card", "upi_qr", "netbanking", "cod"):
        SPECS.append(
            dict(
                id=f"V3-I-{impl}-{method}",
                base="V21-G02",
                design="independent",
                implementation=impl,
                split=split,
                method=method,
            )
        )
IDS = {s["id"] for s in SPECS}


def digest(obj):
    return hashlib.sha256(
        json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def track(s):
    if s["family"] in ("railway", "passport", "echallan"):
        return "C"
    if (
        s.get("fault")
        or s.get("qr", "Q0") != "Q0"
        or s.get("authentication_method", "none")
        not in ("none", "external_wallet_handoff")
        or any(f in s.get("features", []) for f in ("shadow", "iframe", "failure"))
    ):
        return "B"
    return "A"


def set_method(s, method):
    s["method"] = method
    s["customer_brief"]["payment"]["method"] = method
    s["expected_values"]["payment_method"] = method
    s["app"] = "PhonePe" if method == "upi_app" else None
    if method == "upi_qr":
        s.update(
            qr="Q0",
            authentication_method="external_wallet_handoff",
            evaluation_mode="handoff",
            expected_outcome="authentication_required",
        )
    else:
        s.pop("qr", None)
        s.update(authentication_method="none", expected_outcome="checkout_ready")


def scenario_research(sid, seed=None, profile_id=None):
    spec = next(x for x in SPECS if x["id"] == sid)
    s = scenario_v21(spec["base"], 2026 if seed is None else seed, profile_id)
    if spec["design"] == "qr":
        set_method(s, "upi_qr")
        s.update(
            fault="qr",
            qr=spec["level"],
            mobile=False,
            platform="desktop_web",
            os="desktop",
            viewport={"width": 1280, "height": 900},
            allow_upi_alternative=False,
        )
        s["supported_payment_methods"] = ["card", "upi_qr"]
        s["controlled_comparison"] = {
            "matrix": "qr",
            "block": spec["base"],
            "factor": "qr_quality",
            "level": spec["level"],
        }
    elif spec["design"] == "auth":
        s.update(
            auth_surface=spec["surface"],
            fault=None if spec["fault"] == "valid" else spec["fault"],
            evaluation_mode=spec["mode"],
            expected_outcome="authentication_required"
            if spec["mode"] == "handoff"
            else "payment_successful_simulation",
        )
        s["controlled_comparison"] = {
            "matrix": "authentication",
            "block": spec["base"],
            "surface": spec["surface"],
            "fault": spec["fault"],
            "mode": spec["mode"],
        }
    elif spec["design"] == "layout":
        # Each pair differs in its named factor, with all other defaults fixed.
        s.update(
            layout="three-page",
            fault=None,
            shadow=False,
            mobile=False,
            platform="desktop_web",
            os="desktop",
            viewport={"width": 1280, "height": 900},
        )
        f, l = spec["factor"], spec["level"]
        if f == "device" and l == "mobile":
            s.update(
                mobile=True,
                platform="mobile_web",
                os="android",
                viewport={"width": 390, "height": 844},
            )
        if f == "layout":
            s["layout"] = l
        if f == "autofill":
            s["research_autofill"] = l
        if f == "density":
            s["research_density"] = l
        if f == "labels" and l == "unfamiliar":
            aliases = {
                "name": "Consignee",
                "email": "Electronic receipt destination",
                "postal": "Postal routing code",
                "address1": "Street and building",
            }
            for field in s["fields"]:
                field["label"] = aliases.get(field["key"], field["label"])
        s["controlled_comparison"] = {
            "matrix": "layout",
            "block": spec["base"],
            "factor": f,
            "level": l,
        }
    elif spec["design"] == "independent":
        s.update(
            fault=None,
            layout="merchant",
            family="generic",
            theme="generic",
            variant=spec["implementation"],
            research_renderer=spec["implementation"],
            supported_payment_methods=["card", "upi_qr", "netbanking", "cod"],
        )
        set_method(s, spec["method"])
        # Each independent merchant prepares a common user-intent contract in a distinct client architecture.
        s["title"] = (
            spec["implementation"].replace("-", " ").title() + " · " + spec["method"]
        )
    s.update(
        id=sid,
        research_release=RELEASE,
        research_track=track(s),
        implementation_family=spec.get("implementation", "shared-v21-client"),
        research_split=spec.get("split", "development"),
        source_class="government-inspired simulation"
        if s["family"] in ("railway", "passport", "echallan")
        else "independently authored synthetic checkout"
        if spec["design"] == "independent"
        else "synthetic provider-inspired interface",
        ground_truth_review="pending",
        creation_date="2026-10-15",
        test_author="CheckoutBench automated author; independent human review pending",
    )
    s["dom_ids"] = {
        key: "f" + hashlib.sha256(f"{sid}:{s['seed']}:{key}".encode()).hexdigest()[:14]
        for key in s["dom_ids"]
    }
    s["payment_order"] = list(s["supported_payment_methods"])
    s["device_supported"] = s["method"] in s["supported_payment_methods"]
    return s


def metadata(s):
    return {
        k: s.get(k)
        for k in (
            "id",
            "title",
            "research_release",
            "research_track",
            "implementation_family",
            "research_split",
            "source_class",
            "family",
            "variant",
            "method",
            "platform",
            "viewport",
            "authentication_method",
            "auth_surface",
            "evaluation_mode",
            "expected_outcome",
            "fault",
            "qr",
            "controlled_comparison",
            "provenance",
            "ground_truth_review",
            "creation_date",
            "test_author",
        )
    } | {
        "scenario_hash": digest(s),
        "seed": s["seed"],
        "profile_id": s["profile"]["id"],
    }


def build_manifest():
    scenarios = [scenario_research(x["id"]) for x in SPECS]
    rows = [metadata(s) for s in scenarios]
    return {
        "release": RELEASE,
        "status": "pilot candidate; not publication approved",
        "seed": 2026,
        "profile": None,
        "tracks": TRACKS,
        "scenarios": rows,
        "scenario_ids": [s["id"] for s in rows],
        "scenario_count": len(rows),
        "environment_count": len({s["family"] for s in rows}),
        "implementation_count": len({s["implementation_family"] for s in rows}),
        "independence_note": "Distinct client implementations share protocol, widgets and server evaluator; independent authorship/review is not claimed.",
        "payment_methods": sorted({s["method"] for s in rows}),
        "manifest_hash": digest(rows),
    }
