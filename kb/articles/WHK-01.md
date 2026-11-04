---
id: WHK-01
title: Setting up webhooks
category: webhooks
updated: 2026-09-02
---
# Setting up webhooks

This article is for developers who want Northwind Pay to notify their server automatically when payments, refunds, settlements, disputes, or orders change state.

## Before you start

- **An HTTPS endpoint** on your server that accepts POST requests. Plain HTTP (non-TLS) URLs and self-signed certificates are not supported, so use a certificate from a trusted authority.
- **A webhook secret**: a random string you choose and keep private. Northwind Pay uses it to sign every request so you can confirm the request is genuine.
- **A list of the events** your integration needs. See WHK-04.

If your server sits behind a firewall, allow incoming requests from Northwind Pay's published webhook IP list.

## Adding a webhook endpoint

1. Log in to the Dashboard and select test or live mode.
2. Go to Settings > Webhooks.
3. Click Add Endpoint.
4. Enter your HTTPS URL.
5. Enter your webhook secret.
6. Select the events to subscribe to, such as `payment.captured`, `payment.failed`, and `refund.processed`.
7. Save the endpoint.

You can add up to 10 endpoints per account. You might use separate endpoints for different systems, for example one for order fulfillment and one for accounting.

## Building your endpoint

Your endpoint should:

- **Verify the signature** in the `X-Northwind-Signature` header before trusting the request. See WHK-02.
- **Respond quickly**: return a 2xx status within 5 seconds. Acknowledge the event first, then do slow work, such as sending emails, in a background job.
- **Handle duplicates**: the same event may be delivered more than once. Use the `X-Northwind-Event-Id` header to skip events you have already processed.
- **Not depend on order**: if order matters, fetch the current state of the payment or refund through the API.

If your endpoint does not return a 2xx status within 5 seconds, the delivery is retried. See WHK-03.

## Testing your setup

Configure an endpoint in test mode first and make a test payment. Then open Settings > Webhooks > Logs to confirm the delivery and see your server's response. Use the Resend button there to send the same event again while you debug.

## Still need help?

Email support@northwindpay.example with your endpoint URL, the event ID from the `X-Northwind-Event-Id` header, and the related payment ID (`pay_...`). See also: WHK-02, WHK-03, WHK-04.
