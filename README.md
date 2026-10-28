# glueup-tools

A Python client and command-line tool for the [Glue Up](https://www.glueup.com/) open API v2,
written by [IPTC](https://iptc.org/) to connect our Glue Up membership directory to our other
systems. We've published it in case it's useful to other Glue Up customers.

- **`glueup` command:** browse members, companies and events from the terminal, as tables or JSON.
- **`GlueUpClient`:** handles Glue Up's request signing, so scripts can call any endpoint.
- **[API notes](docs/api-notes.md):** what we've learned about the API, including where it
  differs from the documentation and what it can't do yet.

Glue Up's own API documentation is at https://glueupapi.docs.apiary.io/.

## Install

```bash
pip install git+https://github.com/iptc/glueup-tools@v0.2.0
```

Or, to work on it:

```bash
git clone https://github.com/iptc/glueup-tools && cd glueup-tools
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Credentials

You need API access from Glue Up: a public key, a private key, a tenant ID and an organisation
ID. Ask your Glue Up account manager. Put them in the environment, or in a `.env` file (copy
[`.env.example`](.env.example)). The command-line tool looks for `.env` in the current folder
and its parents.

## The `glueup` command

```bash
glueup auth-check                         # check the credentials work
glueup members list --limit 10            # members as a table
glueup members list --search smith --json | jq .
glueup members get 1234567                # one member's full record
glueup companies list                     # corporate memberships
glueup events list
glueup events attendees 123456
glueup settings                           # directory visibility settings
glueup raw GET membershipDirectory/settings   # call any endpoint
```

Every listing command takes `--json` for scripting.

## In Python

```python
from glueup import GlueUpClient, fetch_all_glueup_members

client = GlueUpClient()                     # reads GLUEUP_* from the environment
members = fetch_all_glueup_members(client)  # walks the whole directory
for m in members:
    print(m.email, m.given_name, m.family_name, m.company, m.membership_type)

client.post("event/list", json={"projection": ["id", "title"], "offset": 0, "limit": 10})
```

`client.get / post / put / delete` sign each request and raise `GlueUpError` on HTTP errors
or an `errors` payload.

## Licence

MIT. See [LICENSE](LICENSE). Not affiliated with or endorsed by Glue Up.
