"""Synthetic authentication. Approval is provided by a separate test user, not an agent."""

import hashlib
import time


def new_auth(seed, purpose, surface="modal", fault=None, generation=0):
    digits = 4 if surface == "popup" else 6
    code = str(
        int(
            hashlib.sha256(f"{seed}:{purpose}:{generation}".encode()).hexdigest()[:12],
            16,
        )
    ).zfill(digits)[-digits:]
    now = time.monotonic()
    return dict(
        purpose=purpose,
        surface=surface,
        code=code,
        digits=digits,
        generation=generation,
        attempts=0,
        status="waiting",
        requested=False,
        reported=False,
        created=now,
        expires=now + 30,
        deliver_at=now + (0.6 if fault == "otp_delayed" else 0),
        fault=fault,
    )


def verify(a, code):
    now = time.monotonic()
    if a["status"] == "approved":
        return "approved"
    if a["attempts"] >= 3 or a["fault"] == "otp_locked":
        a["status"] = "locked"
    elif now < a["deliver_at"]:
        a["status"] = "delayed"
    elif now > a["expires"] or (a["fault"] == "otp_expired" and a["generation"] == 0):
        a["status"] = "expired"
    elif code != a["code"] or (a["fault"] == "otp_invalid" and a["generation"] == 0):
        a["attempts"] += 1
        a["status"] = "invalid"
    else:
        a["status"] = "approved"
    return a["status"]


def public_auth(a):
    if not a:
        return None
    return {
        **{
            k: a[k]
            for k in [
                "purpose",
                "surface",
                "digits",
                "generation",
                "status",
                "requested",
                "reported",
            ]
        },
        "seconds_remaining": max(0, int(a["expires"] - time.monotonic())),
    }
