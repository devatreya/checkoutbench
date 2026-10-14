from urllib.parse import urlsplit


def allowed_url(url: str, origin: str, token: str) -> bool:
    """Exact origin AND exact per-session paths; no dashboard or arbitrary loopback."""
    try:
        u = urlsplit(url)
        allowed = urlsplit(origin)
        if (u.scheme, u.hostname, u.port) != (
            allowed.scheme,
            allowed.hostname,
            allowed.port,
        ):
            return False
        if u.username or u.password:
            return False
        return u.path in {
            f"/checkout/{token}",
            f"/session/{token}",
            f"/session/{token}/input",
            f"/session/{token}/advance",
            "/assets/checkout.js",
            "/assets/checkout.css",
            "/assets/card.html",
            "/assets/card.js",
            "/assets/v2.js",
            "/assets/v21.js",
            "/assets/v21.css",
            "/assets/v21-extension.js",
            *{
                f"/v21/{token}/{suffix}"
                for suffix in (
                    "state",
                    "action",
                    "qr",
                    "challenge",
                    "component",
                    "gateway",
                    "provider",
                    "verification",
                    "extension",
                )
            },
            "/assets/v2.css",
            "/assets/v2-base.css",
            *{
                f"/v2/{token}/{suffix}"
                for suffix in (
                    "state",
                    "action",
                    "qr",
                    "challenge",
                    "component",
                    "gateway",
                )
            },
        }
    except ValueError:
        return False
