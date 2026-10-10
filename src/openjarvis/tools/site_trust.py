"""Heuristic trust check for a shopping website - no paid API, no key.

Checks a domain's age (RDAP, the open successor to WHOIS; IANA's free bootstrap
registry picks the right registry server), whether HTTPS actually works and the
certificate is valid, whether it redirects plain HTTP to HTTPS, and whether the
TLD is one commonly abused by throwaway scam sites.

This is a SIGNAL, not a verdict: a brand-new domain can be a legitimate new
shop, and a 10-year-old domain can still scam you. The tool says so in every
result and never returns a bare "safe"/"not safe".
"""

from __future__ import annotations

import re
import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
_DOMAIN_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")
# TLDs with a long track record of cheap/free, throwaway registration abused by scam shops.
# A match is one yellow flag among several, never disqualifying by itself.
_RISKY_TLDS = {
    "tk", "ml", "ga", "cf", "gq", "xyz", "top", "work", "click", "link", "support",
    "loan", "download", "racing", "review", "party", "trade", "webcam", "bid", "win", "men",
}
_CACHE_TTL_S = 24 * 3600
_cache: Dict[str, Any] = {"bootstrap": None, "fetched": 0.0}


def _bootstrap() -> Dict[str, List[str]]:
    """TLD -> list of RDAP base URLs, from IANA's registry (cached in-process)."""
    if _cache["bootstrap"] is not None and time.time() - _cache["fetched"] < _CACHE_TTL_S:
        return _cache["bootstrap"]
    resp = httpx.get(_BOOTSTRAP_URL, timeout=10.0)
    resp.raise_for_status()
    table: Dict[str, List[str]] = {}
    for entry in resp.json().get("services", []):
        if len(entry) < 2:
            continue
        tlds, urls = entry[0], entry[1]
        for tld in tlds:
            table[tld.lower()] = [u.rstrip("/") for u in urls if u.startswith("https://")]
    _cache["bootstrap"] = table
    _cache["fetched"] = time.time()
    return table


def _extract_domain(raw: str) -> Optional[str]:
    raw = (raw or "").strip().lower()
    if "://" not in raw:
        raw = "https://" + raw
    host = (urlparse(raw).hostname or "").strip(".")
    # the registrable domain (last two labels) is what RDAP indexes; a bare host is fine too
    parts = host.split(".")
    domain = ".".join(parts[-2:]) if len(parts) >= 2 else host
    return domain if _DOMAIN_RE.match(domain) else None


def _domain_age(domain: str) -> Dict[str, Any]:
    tld = domain.rsplit(".", 1)[-1]
    bases = _bootstrap().get(tld, [])
    if not bases:
        return {"ok": False, "reason": f"RDAP no cubre el dominio .{tld} (frecuente en ccTLDs pequeños)."}
    last_error = "sin servidores RDAP para este TLD"
    for base in bases:
        try:
            resp = httpx.get(f"{base}/domain/{domain}", timeout=8.0, follow_redirects=True)
        except httpx.HTTPError as exc:
            last_error = str(exc)
            continue
        if resp.status_code == 404:
            return {"ok": False, "reason": "el registro RDAP no encuentra este dominio (puede no estar registrado, o justo haberlo sido)."}
        if resp.status_code != 200:
            last_error = f"RDAP respondió {resp.status_code}"
            continue
        events = {e.get("eventAction"): e.get("eventDate") for e in resp.json().get("events", []) if e.get("eventDate")}
        reg = events.get("registration")
        if not reg:
            return {"ok": False, "reason": "el registro RDAP no indica fecha de registro para este dominio."}
        try:
            created = datetime.fromisoformat(reg.replace("Z", "+00:00"))
        except ValueError:
            return {"ok": False, "reason": "fecha de registro con formato inesperado."}
        age_days = (datetime.now(timezone.utc) - created).days
        return {"ok": True, "created": created.date().isoformat(), "age_days": age_days}
    return {"ok": False, "reason": last_error}


def _https_check(domain: str) -> Dict[str, Any]:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=6) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as tls:
                cert = tls.getpeercert()
        not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        return {"ok": True, "valid_cert": True, "expires": not_after.date().isoformat(),
                "expired": not_after < datetime.now(timezone.utc)}
    except ssl.SSLCertVerificationError as exc:
        return {"ok": True, "valid_cert": False, "error": str(exc)}
    except (OSError, socket.timeout) as exc:
        return {"ok": False, "error": str(exc)}


def _http_redirects_to_https(domain: str) -> Optional[bool]:
    try:
        resp = httpx.get(f"http://{domain}", timeout=6.0, follow_redirects=False)
        if resp.status_code in (301, 302, 307, 308):
            return str(resp.headers.get("location", "")).startswith("https://")
        return False
    except httpx.HTTPError:
        return None


@ToolRegistry.register("check_site_trust")
class CheckSiteTrustTool(BaseTool):
    tool_id = "check_site_trust"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="check_site_trust",
            description=(
                "Check basic, free trust signals for a shopping website before Sothe buys from it: "
                "domain age (RDAP registry), whether HTTPS actually works and the certificate is valid, "
                "whether HTTP redirects to HTTPS, and whether the TLD is one often abused by throwaway "
                "scam shops. Give it a bare domain or a URL in 'site'. This is a heuristic signal, NOT a "
                "verdict: relay the flags plainly and always add that he should also check real reviews "
                "(Trustpilot, Google), pay by card or PayPal (never bank transfer to a stranger), and be "
                "wary of prices far below everyone else's."
            ),
            parameters={
                "type": "object",
                "properties": {"site": {"type": "string", "description": "Domain or URL, e.g. 'tienda-rara.com'."}},
                "required": ["site"],
            },
            category="shopping",
            timeout_seconds=30.0,
        )

    def execute(self, **params: Any) -> ToolResult:
        domain = _extract_domain(str(params.get("site", "")))
        if not domain:
            return ToolResult(tool_name=self.tool_id, content="Dame un dominio o URL válido, p. ej. 'tienda.com'.", success=False)

        flags: List[str] = []
        notes: List[str] = []

        try:
            age = _domain_age(domain)
        except Exception as exc:  # the IANA bootstrap or a registry can fail in many ways; never crash the turn
            age = {"ok": False, "reason": str(exc)}
        if age.get("ok"):
            days = age["age_days"]
            notes.append(f"dominio registrado el {age['created']} ({days} días, ~{days // 365} años)")
            if days < 90:
                flags.append(f"dominio MUY reciente (menos de 90 días, desde {age['created']})")
            elif days < 365:
                flags.append(f"dominio reciente (menos de un año, desde {age['created']})")
        else:
            notes.append(f"no se pudo saber la antigüedad del dominio ({age.get('reason', 'desconocido')})")

        https = _https_check(domain)
        if https.get("ok") and https.get("valid_cert"):
            notes.append(f"HTTPS correcto, certificado válido hasta {https['expires']}")
            if https.get("expired"):
                flags.append("el certificado HTTPS está CADUCADO")
        elif https.get("ok"):
            flags.append(f"HTTPS con certificado NO válido ({https.get('error', 'sin detalle')})")
        else:
            flags.append(f"no se pudo conectar por HTTPS al dominio ({https.get('error', 'sin detalle')})")

        redirect = _http_redirects_to_https(domain)
        if redirect is False:
            flags.append("la web NO redirige de HTTP a HTTPS automáticamente")
        elif redirect is None:
            notes.append("no se pudo comprobar la redirección HTTP->HTTPS")

        tld = domain.rsplit(".", 1)[-1]
        if tld in _RISKY_TLDS:
            flags.append(f"dominio .{tld}, un TLD gratuito o barato usado a menudo por tiendas desechables")

        verdict = (
            f"{len(flags)} señal(es) de alerta" if flags else
            "sin señales de alerta en estas comprobaciones básicas (no significa que sea 100% fiable)"
        )
        text = (
            f"Comprobación de {domain}: {verdict}. "
            + ("Alertas: " + "; ".join(flags) + ". " if flags else "")
            + "Detalle: " + "; ".join(notes) + ". "
            "Esto es solo una señal automática (edad del dominio, HTTPS y el TLD): no sustituye mirar reseñas "
            "reales (Trustpilot, Google), pagar con tarjeta o PayPal (nunca transferencia a un desconocido) "
            "y desconfiar de precios muy por debajo del resto."
        )
        return ToolResult(tool_name=self.tool_id, content=text, success=True,
                           metadata={"domain": domain, "flags": flags})
