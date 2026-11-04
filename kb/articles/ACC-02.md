---
id: ACC-02
title: Two-factor authentication problems
category: account_access
updated: 2026-06-18
---
# Two-factor authentication problems

This article helps you if you cannot complete two-factor authentication (2FA) when logging in to the Dashboard, or if you have lost the device you use for 2FA.

## How 2FA works on Northwind Pay

You can use either an authenticator app that generates time-based codes (TOTP) or an OTP sent by SMS to your registered phone. 2FA is mandatory for the Owner and Admin roles and recommended for everyone else.

When you turn on 2FA, you receive 10 one-time backup codes. Each code works only once. Store them somewhere safe and separate from your phone, such as a password manager.

## Codes are not working

- **Authenticator app codes rejected**: TOTP codes depend on the time on your phone. Turn on automatic date and time in your phone's settings, then try a fresh code.
- **SMS OTP not received**: check your signal, make sure the registered phone number is correct, and wait briefly before requesting another code. Always use the most recent OTP.
- **Repeated failures**: too many failed login attempts can lock your account for a while. See ACC-03.

If codes still fail, log in with one of your backup codes, then set up 2FA again on your current device.

## Lost device and no backup codes

**If you are a team member**: ask your account Owner to reset 2FA for you. You can then log in and set up 2FA again on your new device.

**If you are the account Owner**: contact support to verify your identity. You will need:

1. A government-issued ID
2. Your registered email address
3. Your registered phone number

Identity verification takes 1-2 business days. Once it is complete, support resets 2FA so you can set it up again.

## Protect yourself from scams

Northwind Pay support never asks for your password, OTPs, or backup codes. If anyone contacts you asking for them, even if they claim to be from Northwind Pay, do not share them. Report the contact to support@northwindpay.example.

## Still need help?

Email support@northwindpay.example from your registered email address with your business name and Dashboard user email, but never any codes or passwords. See also: ACC-01, ACC-03, ACC-04.
