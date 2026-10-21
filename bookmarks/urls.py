"""Conservative URL syntax validation; this does not authorize any fetch."""
import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit

from .errors import InvalidURLError


_BAD_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
_ENCODED_CONTROL = re.compile(r"%(?:0[0-9a-f]|1[0-9a-f]|7f)", re.IGNORECASE)
_DNS_LABEL = re.compile(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\Z")


def validate_url(url: str) -> str:
    """Accept supported HTTP(S) syntax and return the exact original string.

    No trimming, case folding, port removal, decoding, or query/fragment changes
    are used for identity. Local/private destinations are syntactically valid;
    later network code must separately enforce destination/redirect/SSRF rules.
    """
    if not isinstance(url, str) or not url:
        raise InvalidURLError()
    # urlsplit silently removes some controls; reject them before parsing.
    if any(c.isspace() or unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in url):
        raise InvalidURLError()
    if any(c in url for c in '\\"<>`{}|^') or _BAD_ESCAPE.search(url) or _ENCODED_CONTROL.search(url):
        raise InvalidURLError()
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            raise ValueError()
        if parts.username is not None or parts.password is not None:
            raise ValueError()
        host = parts.hostname
        if not host or "%" in host:
            raise ValueError()
        # Reading .port validates numeric syntax/range; reject empty ports too.
        port = parts.port
        if parts.netloc.endswith(":"):
            raise ValueError()
        if parts.netloc.startswith("["):
            ipaddress.IPv6Address(host)
            tail = parts.netloc[parts.netloc.index("]") + 1:]
            if tail and (not tail.startswith(":") or port is None):
                raise ValueError()
        else:
            ascii_host = host.encode("idna").decode("ascii").removesuffix(".")
            if len(ascii_host) > 253 or not all(_DNS_LABEL.fullmatch(label) for label in ascii_host.split(".")):
                raise ValueError()
            # Browsers interpret numeric final labels as IPv4, not DNS names.
            # Accept only strict dotted-decimal notation; never repair identity.
            if re.fullmatch(r"(?:[0-9]+|0[xX][0-9a-fA-F]*)", ascii_host.rsplit(".", 1)[-1]):
                ipaddress.IPv4Address(ascii_host)
    except (ValueError, UnicodeError):
        raise InvalidURLError() from None
    return url
