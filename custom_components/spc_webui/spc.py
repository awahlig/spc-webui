import logging
import re
import ssl
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx


# Page: any
RE_TITLE = re.compile(
    r"<title>([^<]+?)</title>",
    re.IGNORECASE
)

# Page: any after logging in
RE_SERIAL = re.compile(
    r"S/N:\s*([0-9A-Za-z]+)"
)
RE_SESSION = re.compile(
    r"(?:\?|&)session=(0x[0-9A-Fa-f]+)"
)

# Page: login
RE_LOGIN = re.compile(
    r"\baction=login\b",
    re.IGNORECASE
)
RE_DENIED = re.compile(
    r"\bAccess\s+denied\b",
    re.IGNORECASE
)

# Page: system_summary
RE_ARM_STATE = re.compile(
    r">All Areas</td><td[^>]*>([^<]+)</td>",
    re.IGNORECASE,
)
RE_IMPORTANT = re.compile(
    r"<font[^>]*color=red[^>]*><b>(.*?)</b></font>",
    re.IGNORECASE | re.DOTALL
)

# Page: status_zones
RE_ZONE = re.compile(
    r"<TR\s+HEIGHT=20>"
    # (1) zone id, (2) zone name
    r"\s*<TD\s+ALIGN=\"center\">(\d+)\s+([^<]+)</TD>"
    # (3) area id, (4) area name
    r"\s*<TD\s+ALIGN=\"center\">(\d+)\s+([^<]+)</TD>"
    # (5) zone type
    r"\s*<TD\s+ALIGN=\"center\">([^<]+)</TD>"
    # (6) (commented out) input state
    r".*?<!--.*?<font[^>]*>(?:<b>)?([^<]+)(?:</b>)?</font>.*?-->"
    # (7) status
    r"\s*<TD\s+ALIGN=\"center\"><FONT\s+COLOR=\w+>(?:<B>)?([^<]+)(?:</B>)?</FONT></TD>",
    re.IGNORECASE | re.DOTALL
)

LOGGER = logging.getLogger(__name__)


def get_ssl_context():
    """
    SSL context compatible with legacy SPC panels.

    SPC typically requires:
    - TLS 1.2 only
    - invalid/self-signed cert acceptance
    - legacy RSA cipher (AES256-SHA) at lower OpenSSL security level
    - legacy renegotiation allowance (if available)
    """

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2

    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Legacy cipher + lower seclevel (key for OpenSSL 3.x)
    try:
        ctx.set_ciphers("AES256-SHA:@SECLEVEL=1")
    except ssl.SSLError:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")

    opt = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", None)
    if opt is not None:
        ctx.options |= opt
    else:
        LOGGER.warning("SSL lacks OP_LEGACY_SERVER_CONNECT; SPC handshake may fail")

    return ctx


def normalize_url(url, default_scheme="https"):
    """Add default scheme if missing."""
    parsed = urlparse(url)
    if not parsed.scheme:
        return f"{default_scheme}://{url}"
    return url


def parse_title(html):
    """Return [model, site] parsed from the HTML title, falling back to blanks."""
    re_match = RE_TITLE.search(html)
    if re_match:
        result = (re_match.group(1).split(" - ", 1) + [""])[:2]
    else:
        result = ("", "")
    return [s.strip() for s in result]


def parse_serial_number(html):
    """Extract the SPC serial number if present; return empty string otherwise."""
    re_match = RE_SERIAL.search(html)
    return (re_match.group(1) if re_match else "")


def parse_session_id(html):
    """Get the session token from a WebUI page or raise if missing."""
    re_match = RE_SESSION.search(html)
    if re_match:
        return re_match.group(1)
    raise SPCParseError("Session ID not found in HTML")


def parse_arm_state(html):
    """Pull out the arm state text from the system summary page."""
    re_match = RE_ARM_STATE.search(html)
    if re_match:
        return re_match.group(1).strip().lower()
    raise SPCParseError("Arm state not found in HTML")


def parse_important_message(html):
    """Pull out the red banner message. Returns None if not found."""
    re_match = RE_IMPORTANT.search(html)
    if re_match:
        return re_match.group(1).strip()


def parse_zones(html):
    """Pull out the zones."""
    for m in RE_ZONE.finditer(html):
        yield {
            "zone_id": int(m.group(1)),
            "zone_name": m.group(2).strip(),
            "area_id": int(m.group(3)),
            "area_name": m.group(4).strip(),
            # Alarm, Entry/Exit, ...
            "zone_type": m.group(5).strip().lower(),
            # For inhibited zones, this shows the underlying status
            # Open, Closed, DISCON, ...
            "input": m.group(6).strip().lower(),
            # Normal, Tamper, Inhibit, ...
            "status": m.group(7).strip().lower(),
        }


def is_login_page(html):
    return bool(RE_LOGIN.search(html))


def is_access_denied(html):
    return bool(RE_DENIED.search(html))


class SPCError(Exception):
    pass


class SPCParseError(SPCError):
    pass


class SPCLoginError(SPCError):
    pass


class SPCCommandError(SPCError):
    pass


class SPCSession:
    """Async helper around the SPC WebUI session workflow and HTML parsing."""

    def __init__(self, url, userid, password):
        self._userid = userid
        self._password = password

        self.client = httpx.AsyncClient(
            base_url=normalize_url(url),
            verify=get_ssl_context(),
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(
                max_connections=1,
                max_keepalive_connections=0,
            ),
        )

        self.creds = {
            "userid": userid,
            "password": password,
        }

        self.sid = ""
        self.model = ""
        self.serial_number = ""
        self.site = ""

    async def aclose(self):
        """Close the underlying HTTPX client."""
        await self.client.aclose()

    def _get_secure_url(self, page, update=False):
        action = ("&action=update" if update else "")
        return f"/secure.htm?session={self.sid}&page={page}&language=0{action}"

    def _get_html(self, resp):
        resp.raise_for_status()
        html = resp.text
        self.model, self.site = parse_title(html)
        return html

    async def _do_with_login(self, do):
        if self.sid:
            html = await do()
            if not is_login_page(html):
                return html
        await self.login()
        return await do()

    async def login(self):
        """Log in and populate session ID, serial number, model, and site."""
        url = "/login.htm?action=login&language=0"
        resp = await self.client.post(url, data=self.creds)
        html = self._get_html(resp)

        if is_login_page(html):
            if is_access_denied(html):
                raise SPCLoginError("SPC login failed: access denied")
            raise SPCLoginError("SPC login failed: still on login page")

        self.sid = parse_session_id(html)
        self.serial_number = parse_serial_number(html)

    async def get_arm_state(self):
        """Fetch current global arm state."""
        async def do():
            url = self._get_secure_url("system_summary")
            resp = await self.client.get(url)
            return self._get_html(resp)

        html = await self._do_with_login(do)
        return parse_arm_state(html)

    async def set_arm_state(self, arm_state):
        """Send a command to change the global arm state."""
        if arm_state == "unset":
            data = {"unset_all_areas": "Unset"}
        elif arm_state == "fullset":
            data = {"fullset_area1": "Fullset"}
        elif arm_state == "forceset":
            data = {"fullset_force1": "Force set"}
        else:
            raise SPCCommandError(f"{arm_state}: unknown arm state")

        async def do():
            url = self._get_secure_url("system_summary", update=True)
            resp = await self.client.post(url, data=data)
            return self._get_html(resp)

        html = await self._do_with_login(do)
        msg = parse_important_message(html)
        if msg:
            raise SPCCommandError(msg)
        return parse_arm_state(html)

    async def get_zones(self):
        """Fetch a list of zones."""
        async def do():
            url = self._get_secure_url("status_zones")
            resp = await self.client.get(url)
            return self._get_html(resp)

        html = await self._do_with_login(do)
        return list(parse_zones(html))

    async def set_zone_inhibit(self, zone_id, inhibit):
        """Inhibit/deinhibit a zone."""
        if inhibit:
            data = {f"inhibit{zone_id}": "Inhibit"}
        else:
            data = {f"uninhibit{zone_id}": "Deinhibit"}

        async def do():
            url = self._get_secure_url("status_zones", update=True)
            url += "&zone=1"  # XXX webui always sends this for some reason
            resp = await self.client.post(url, data=data)
            return self._get_html(resp)

        html = await self._do_with_login(do)
        return next((zone for zone in parse_zones(html)
                     if zone["zone_id"] == zone_id), None)
