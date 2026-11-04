---
id: API-01
title: Generating and regenerating API keys
category: api_keys
updated: 2026-08-12
---
# Generating and regenerating API keys

This article is for developers and account administrators who need to create API keys for the first time, or replace a key whose secret has been lost or exposed.

## Who can manage API keys

Only users with the Owner or Admin role can view or regenerate API keys. If you have the Developer, Finance, Support, or Viewer role, ask your account Owner or an Admin to generate keys and share them with you through a secure channel.

Each key pair has two parts:

- **Key ID**: starts with `nw_test_` in test mode or `nw_live_` in live mode. It identifies the key but does not authenticate on its own.
- **Key Secret**: the password used to authenticate API requests. Store it in a secrets manager or environment variable, never in client-side code or a public repository.

Live keys are available only after your KYC is verified.

## Generating a new key pair

1. Log in to the Dashboard at dashboard.northwindpay.example.
2. Switch to test mode or live mode, depending on which keys you need.
3. Go to Settings > API Keys.
4. Click Generate Key.
5. Copy the Key ID and Key Secret and store them securely right away.

The Key Secret is shown only once, at the moment it is generated. Northwind Pay cannot display it again or recover it for you. If you close the window without saving it, you will need to regenerate the key.

## Regenerating a key

Regenerate your key if the secret is lost, if you suspect it has been exposed, or as part of routine rotation.

1. Go to Settings > API Keys.
2. Click Regenerate next to the key.
3. Choose whether to invalidate the old secret immediately or keep it valid during the optional 24-hour grace period.
4. Copy and store the new Key Secret.
5. Update the secret in every server and service that calls the API.

By default, regenerating immediately invalidates the old secret. Use the grace period when you need time to deploy the new secret across several systems without downtime. If you believe the secret has leaked, skip the grace period so the exposed secret stops working at once.

## Still need help?

Contact support@northwindpay.example with your Key ID (never your Key Secret), whether you are in test or live mode, and the time of the change. See also: API-02, API-03, ACC-04.
