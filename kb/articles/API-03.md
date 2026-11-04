---
id: API-03
title: Fixing 401 authentication errors
category: api_keys
updated: 2026-08-20
---
# Fixing 401 authentication errors

This article is for developers whose API requests are returning `401 AUTHENTICATION_ERROR`. It explains how authentication works and how to find the cause.

## How API authentication works

The Northwind Pay API uses HTTP Basic authentication. Send your Key ID as the username and your Key Secret as the password with every request to api.northwindpay.example/v1. Most HTTP libraries build the `Authorization` header for you when you pass a username and password.

A `401 AUTHENTICATION_ERROR` means the API could not match the credentials you sent to a valid key pair.

## Common causes

- **Wrong key**: the Key Secret does not belong to the Key ID, or the key has been regenerated and the old secret is no longer valid.
- **Mixed test and live keys**: a `nw_test_` Key ID paired with a live secret, or a `nw_live_` Key ID paired with a test secret.
- **Whitespace in the secret**: a leading or trailing space, tab, or newline copied along with the secret, often from a terminal, spreadsheet, or `.env` file.
- **Grace period ended**: if the key was regenerated with the optional 24-hour grace period, the old secret stops working once that period ends.
- **Missing credentials**: the request was sent without Basic auth, for example because an environment variable was not loaded.

## How to troubleshoot

1. Log the Key ID your server is actually sending (never log the Key Secret). Confirm it has the prefix for the mode you intend to use.
2. Check in Dashboard > Settings > API Keys that the Key ID exists in that mode and has not been regenerated recently. Only Owner and Admin users can view this page.
3. Trim whitespace from the stored Key Secret and reload your configuration.
4. Send a simple authenticated request from the same server with a command-line HTTP client and the same credentials.
5. If the secret may be wrong or lost, regenerate the key and update every service that uses it. The new Key Secret is shown only once, so store it immediately.

## Related errors that are not 401

- `403 IP_NOT_ALLOWED`: your credentials are valid, but the request came from an IP address that is not on your allowlist.
- `429 RATE_LIMITED`: you exceeded the rate limit. Wait for the time given in the `Retry-After` header before retrying.

## Still need help?

Contact support@northwindpay.example with the Key ID, the mode (test or live), the approximate time of the failed request, and your server's outbound IP. Never share your Key Secret. See also: API-01, API-02, API-04.
