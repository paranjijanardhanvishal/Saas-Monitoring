"""Generate clearly-labelled test traffic through the local mitmproxy.

TLS verification is never disabled. Because mitmproxy re-signs HTTPS traffic,
the mitmproxy CA certificate must be trusted by the client first:

    set REQUESTS_CA_BUNDLE=C:\\path\\to\\mitmproxy-ca-cert.pem

The bearer token below is a fake value used only to produce request metadata.
No real Google credentials are required or transmitted. This script does not
assert that events were persisted; verify that in the Live Activity page.
"""

import os
import sys
import uuid

import requests

PROXY_URL = os.getenv("PROXY_URL", "http://127.0.0.1:8080")
PROXIES = {"http": PROXY_URL, "https": PROXY_URL}

TEST_TOKEN = "fake-test-token-not-a-real-credential"
HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "Content-Type": "application/json",
}

CA_BUNDLE = os.getenv("REQUESTS_CA_BUNDLE")

if not CA_BUNDLE or not os.path.exists(CA_BUNDLE):
    print(
        "REQUESTS_CA_BUNDLE must point to the mitmproxy CA certificate. "
        "TLS verification is intentionally not disabled."
    )
    sys.exit(2)


def send(label, method, url, **kwargs):
    print(f"\n[{label}] {method} {url}")
    try:
        response = requests.request(
            method,
            url,
            headers=HEADERS,
            proxies=PROXIES,
            verify=CA_BUNDLE,
            timeout=15,
            **kwargs,
        )
        print(f"Proxy forwarded request; origin responded HTTP {response.status_code}.")
    except requests.RequestException as exc:
        print(f"Request failed: {type(exc).__name__}")


def main():
    print(f"Routing test traffic through {PROXY_URL}")
    file_id = f"test_file_{uuid.uuid4().hex[:8]}"

    send(
        "UPLOAD",
        "POST",
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=media",
        data=b"test metadata only",
    )
    send("ACCESS", "GET", f"https://www.googleapis.com/drive/v3/files/{file_id}")
    send(
        "DOWNLOAD",
        "GET",
        f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
    )
    send(
        "PERMISSION_CHANGE",
        "POST",
        f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
        json={"role": "reader", "type": "anyone"},
    )
    send("DELETE", "DELETE", f"https://www.googleapis.com/drive/v3/files/{file_id}")
    print("\nTest traffic generation complete. Check Live Activity for persisted events.")


if __name__ == "__main__":
    main()
