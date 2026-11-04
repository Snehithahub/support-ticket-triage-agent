---
id: API-04
title: Rate limits and IP allowlisting
category: api_keys
updated: 2026-08-20
---
# Rate limits and IP allowlisting

This article is for developers who are seeing `429 RATE_LIMITED` or `403 IP_NOT_ALLOWED` responses, or who want to restrict API access to known servers.

## Rate limits

The Northwind Pay API allows 25 requests per second per account. The limit applies to the account as a whole, so all of your servers and services share it.

If you exceed the limit, the API returns `429 RATE_LIMITED` with a `Retry-After` header. The header tells you how long to wait before sending the request again.

## Handling 429 responses

1. Read the `Retry-After` header on every 429 response.
2. Pause requests from that client for at least the time indicated, then retry.
3. For repeated 429 responses, add exponential backoff with jitter so multiple workers do not retry at the same moment.
4. Make sure retried requests are safe to repeat. For example, check whether a refund was already created before creating it again.

To stay under the limit:

- Rely on webhooks for payment and refund status instead of polling the API in a loop.
- Spread bulk jobs, such as reconciliation scripts, over time instead of running them in parallel bursts.
- Cache data that does not change often.

## IP allowlisting

IP allowlisting is optional. When it is turned on, the API accepts requests only from the addresses you list. You can add up to 20 IP addresses or CIDR ranges.

Requests from any other address receive `403 IP_NOT_ALLOWED`, even if the API key is valid.

To set it up:

1. Find the outbound IP addresses of every server that calls the API, including staging, batch jobs, and failover environments.
2. In the Dashboard, open the IP allowlist settings for your API access.
3. Add each address or CIDR range and save.
4. Send a test request from each server to confirm it is accepted.

If you start getting `403 IP_NOT_ALLOWED` after a deployment or infrastructure change, check whether your hosting provider changed your outbound IP. The allowlist applies to API requests you send to Northwind Pay; it does not affect webhooks that Northwind Pay sends to you.

## Still need help?

Contact support@northwindpay.example with your Key ID (never the Key Secret), the error code, the time of the request, and the IP address it was sent from. See also: API-01, API-03, WHK-03.
