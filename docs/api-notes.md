# Notes on the Glue Up open API v2

What we've learned building IPTC's integrations (October 2026). Corrections and additions are
welcome as issues or pull requests.

## Authentication

Every request carries an `a` header signed with HMAC-SHA256:

```
digest = hex(hmac_sha256(key=privateKey, msg=METHOD + publicKey + "1.0" + timestampMs))
a: v=1.0;k=<publicKey>;ts=<timestampMs>;d=<digest>
```

plus `tenantId` (the top-level account) and `requestOrganizationId` (the organisation within
it). The timestamp must be recent: requests signed more than about 20 minutes earlier are
rejected with error code -1005, so sign each request rather than reusing a header.
`GlueUpClient` does all of this.

## Where the API differs from the documentation

- **Response envelope.** The docs describe `{"code": ..., "data": {"value", "errors",
  "warnings", "metadata"}}`. The live API returns `value`, `errors`, `warnings` and `metadata`
  at the top level, with no `data` wrapper or `code`; the HTTP status is the real result. The
  client accepts both shapes.
- **Membership type list.** The documentation lists "Retrieve the Membership Type List By
  Page", but we haven't found a path for it that works.

## What the API can't do (yet)

These are the gaps we've hit. Each one is a feature we'd like to see.

- **No member writes.** Members can be read but not created, updated or deleted, so changes
  made in other systems can't flow back into Glue Up.
- **No change tracking.** Member records have no `lastModified` (even when it's requested in
  the projection), so every sync has to fetch the whole directory and compare.
- **No webhooks** in the v2 documentation, so other systems can't react to a new, renewed or
  lapsed member; they have to poll.
- **No groups on members.** Member and company records don't show tags, committees or working
  groups, and their `properties` field comes back empty, so routing members to the right
  mailing lists or Slack channels needs a mapping kept elsewhere.
- **No list of subscription lists.** `subscription/subscribeLists` needs subscription list IDs,
  but there's no endpoint to find them.
- **No email campaign endpoints.**
- **Rate limits aren't documented.**

## Useful endpoints

| Call | What it does |
|---|---|
| `GET membershipDirectory/settings` | Directory visibility settings; a cheap way to test credentials |
| `POST membershipDirectory/members` | Page through individual members (`offset`, `limit`, optional `search`) |
| `GET membershipDirectory/member/{id}` | One member |
| `POST membershipDirectory/corporateMemberships` | Page through company memberships (`/basic` for a lighter version) |
| `GET membershipDirectory/corporate/{id}` | One company |
| `POST event/list` | Events, with `projection`, `filter` and `order` |
| `POST event/{id}/attendeeList` | An event's attendees |
