# ADR 0010: directory sign-in on python-ldap alone, not django-auth-ldap

Date: 2026-09-03
Status: accepted, and the maintainer may reverse it

## The question

The Phase 1 specification's Sign-in chapter says, under Libraries: "A fresh
implementation on django-auth-ldap with python-ldap, versions pinned at build
time". The build has used python-ldap and not django-auth-ldap.

## What the specification asks for, and what it also asks for

The same chapter fixes several things that django-auth-ldap does not do:

- **A failed sign-in must record which kind of failure it was.** The audit
  log's reason classes are `wrong_password`, `not_in_a_group`, `deactivated`,
  `blocked`, `directory_unreachable`, and `throttled`, and the person is told
  different things for a wrong password and an unreachable directory.
  django-auth-ldap's backend returns `None` for every one of them: a wrong
  password, a person outside both groups, a disabled account, and a domain
  controller that did not answer are one answer to the caller.
- **The Directory check reads each group's member list** and writes a
  membership snapshot and one row per change. django-auth-ldap answers "is
  this person in that group" during a sign-in; it does not enumerate a group.
- **The four checks of Test directory connection** bind, read both groups,
  resolve a member of each, and prove the nested rule, reporting each as pass
  or fail with the directory's own words. That is a diagnostic tool, not an
  authentication backend.

Every one of those is written against python-ldap either way. What
django-auth-ldap would have added on top is a Django authentication backend
that this app does not use: the app has its own sign-in path, with its own
throttle, its own refusals, its own audit rows, and its own Login session.

## The decision

python-ldap only, pinned. The connection follows the chapter exactly: LDAPS to
`LDAP_SERVER_URI`, the CA file option pointing at `LDAP_CA_FILE`, a 5-second
`OPT_NETWORK_TIMEOUT`, the Bind account and its password file, `sAMAccountName`
as the sign-in name, `userPrincipalName` as the identity kept, and group
membership by the in-chain `member` filter (`1.2.840.113556.1.4.1941`), never
`memberOf`. An empty password is never sent.

## What is given up

django-auth-ldap is a well-worn library with its own tests, and using it would
mean less of this app's own code to be wrong. Against that: its configuration
would still have to be read and understood, and everything it does here is
about fifty lines of python-ldap that the app needs anyway for the Directory
check and the four checks.

## What would change it

The maintainer's word. If the office would rather stand on the more widely
used library, the sign-in path can be moved onto `LDAPBackend` and keep the
reason classes by asking the directory the same questions afterwards; the
Directory check and the four checks stay as they are either way.
