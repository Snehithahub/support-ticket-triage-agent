---
id: WHK-03
title: Webhook retries and failed deliveries
category: webhooks
updated: 2026-09-10
---
# Webhook retries and failed deliveries

This article explains what happens when your server does not acknowledge a webhook, how to find failed deliveries, and how to recover a disabled endpoint.

## What counts as a successful delivery

A delivery succeeds when your endpoint returns a 2xx status code within 5 seconds. Anything else counts as a failure, including:

- A non-2xx status, such as a 4xx or 5xx error
- A response that takes longer than 5 seconds
- A connection, DNS, or TLS problem, such as an expired or self-signed certificate

## Retry schedule

Failed deliveries are retried automatically with exponential backoff for up to 24 hours, which is about 12 attempts. The gap between attempts grows over time, so a short outage on your side is usually recovered by the early retries.

If deliveries keep failing for 24 hours, Northwind Pay disables the endpoint and emails the account owner. No further events are sent to a disabled endpoint until you fix the problem and enable it again in Dashboard > Settings > Webhooks.

## Finding and resending failed deliveries

1. Go to Dashboard > Settings > Webhooks > Logs. Delivery logs cover the last 30 days.
2. Find the failed attempts for your endpoint.
3. Open an attempt to see the response status and timing your server returned.
4. Fix the underlying issue on your server.
5. Click Resend to deliver the event again.

After re-enabling a disabled endpoint, review the logs for events missed while it was down and resend them, or fetch the current state of the affected payments and refunds through the API.

## Handling duplicate deliveries

Because of retries and resends, the same event can reach your server more than once. Each event has a unique `X-Northwind-Event-Id` header. Store the IDs you have processed and skip any event whose ID you have already seen. This stops actions such as marking an order paid or sending a receipt from running twice.

To avoid timeouts, return a 2xx response as soon as you have verified the signature and recorded the event ID, then do the rest of the work in a background job.

## Still need help?

Email support@northwindpay.example with the endpoint URL, the `X-Northwind-Event-Id` of a failed delivery, and the response status shown in the logs. See also: WHK-01, WHK-02, WHK-04.
