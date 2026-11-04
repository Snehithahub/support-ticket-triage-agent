---
id: WHK-02
title: Verifying webhook signatures
category: webhooks
updated: 2026-09-02
---
# Verifying webhook signatures

This article is for developers who need to confirm that webhook requests really come from Northwind Pay and have not been changed in transit.

## How signing works

Every webhook request includes an `X-Northwind-Signature` header. Its value is a hex-encoded HMAC-SHA256 of the raw request body, computed with the webhook secret you set in Dashboard > Settings > Webhooks.

To verify a request, compute the same HMAC on your side and compare it with the header. If they match, the request is genuine. If they do not match, reject the request and do not process the event.

## Python example

```python
import hmac
import hashlib

def is_valid_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

Pass the exact bytes of the request body and the value of the `X-Northwind-Signature` header. In Flask, for example, read the raw body with `request.get_data()`. If the function returns `False`, respond with an error status and stop.

## Common mistakes

- **Re-serialized JSON**: parsing the body and converting it back to a string can change spacing and key order, so the signature will not match. Always verify against the raw body bytes, before any JSON parsing.
- **Plain string comparison**: comparing with `==` can leak timing information. Use a constant-time comparison such as `hmac.compare_digest`.
- **Wrong secret**: the webhook secret is not your API Key Secret. Check that you are using the secret configured for this endpoint and for the correct mode (test or live).
- **Stray whitespace**: trim spaces and newlines from the stored secret and from the header value.
- **Middleware altering the body**: some frameworks decode or modify the body before your handler runs. Capture the raw body before that happens.

## After verification

Once the signature is valid, check the `X-Northwind-Event-Id` header and skip events you have already processed, since the same event can be delivered more than once. Then return a 2xx status within 5 seconds and do any slow work in the background.

## Still need help?

Contact support@northwindpay.example with your endpoint URL, the `X-Northwind-Event-Id` of a failing request, and the time it was received. Never send your webhook secret. See also: WHK-01, WHK-03, WHK-04.
