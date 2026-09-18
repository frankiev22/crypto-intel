# Security

## ⛔ Do not put secrets in issues, pull requests or discussions

This repository is public. Anything posted here is public immediately and
permanently, and deleting it afterwards does not un-publish it — it has already
been cloned, cached and indexed.

**Never paste into this repo:** API keys, webhook URLs, wallet private keys or
seed phrases, `.env` contents, or database credentials. If you do so by
accident, **rotate the credential first** and then tell us. Removing it from
history is the second step, not the first, and on its own it fixes nothing.

## Reporting a vulnerability

Open an issue describing the problem **without** including the credential or
payload that demonstrates it.

## What is in this repo by design

`site/index.html` contains a Supabase project URL and its **publishable** key.
That is the intended use of a publishable key — it ships in client code and is
already served publicly by the deployed page. It is scoped read-denied: a
`SELECT` against it returns `401 / 42501 insufficient privilege`.

No private key, service-role key, or `.env` file has ever been committed. This
was verified before the repository was made public by scanning all 216 commits
and 6,932 objects for the literal value of every credential in `.env`, plus nine
generic secret patterns.

## Note on the data

`data/` contains **simulated** paper trades. There are no wallets, transaction
signatures, or real positions anywhere in this repository, and no trade
execution code exists in it.
