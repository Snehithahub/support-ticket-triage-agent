---
id: CHK-01
title: Integrating Standard Checkout
category: checkout
updated: 2026-09-22
---
# Integrating Standard Checkout

This article is for developers adding Northwind Pay Standard Checkout to a website. It explains the order flow and how to verify each payment on your server before you fulfil the order.

## How the flow works

Standard Checkout runs in the customer's browser, but the order and the final verification happen on your server:

1. **Create an order on your server.** Call `POST /v1/orders` with the amount in paise and currency `INR`. Add `payment_capture: 1` if you want payments captured automatically.
2. **Open checkout in the browser.** Load `https://checkout.northwindpay.example/v1/checkout.js` and pass the `order_id` returned in step 1 together with your Key ID. Never put your Key Secret in browser code.
3. **Receive the result.** When the payment succeeds, checkout returns `northwind_payment_id`, `northwind_order_id` and `northwind_signature` to your success handler.
4. **Verify on your server.** Send those three values to your backend and check the signature before marking the order as paid.

Use keys from the same mode for every step. An order created with a test key cannot be paid with a live Key ID.

## Verify the payment signature

The signature is a hex HMAC-SHA256 of `order_id + "|" + payment_id`, computed with your Key Secret. Use the `order_` ID returned by Northwind Pay, not the order number from your own database.

```python
import hmac
import hashlib

def verify_payment(order_id: str, payment_id: str, signature: str, key_secret: str) -> bool:
    message = f"{order_id}|{payment_id}".encode("utf-8")
    expected = hmac.new(
        key_secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

If the function returns `False`, do not fulfil the order. Log the IDs and investigate; see CHK-02 for common causes.

## Capturing payments

- **Auto-capture:** with `payment_capture: 1`, successful payments move to `captured` without any further call.
- **Manual capture:** without it, payments stay `authorized` until you capture them. Authorized payments not captured within 5 days are auto-voided and the customer's bank releases the hold.

Do not rely only on the browser success handler. Customers sometimes close the tab before it runs, so also subscribe to the `payment.captured` and `order.paid` webhooks.

## Still need help?

Email support@northwindpay.example with the order ID (`order_...`), the payment ID (`pay_...`), and whether you are in test or live mode. Never share your Key Secret. See also: CHK-02, WHK-05, API-02.
