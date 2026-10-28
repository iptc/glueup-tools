"""Glue Up CLI: a `gh`/`wp`-style command-line wrapper.

Run `glueup --help` once installed.
"""

from __future__ import annotations

import json as _json
import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Look for .env in cwd and walk up — convenient when invoked from anywhere
load_dotenv()
if not (Path.cwd() / ".env").exists():
    for parent in Path.cwd().parents:
        env = parent / ".env"
        if env.exists():
            load_dotenv(env)
            break

from .client import GlueUpClient, GlueUpError  # noqa: E402

app = typer.Typer(
    help="Command-line tool for the Glue Up API. Pretty tables by default; --json for pipelines.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()
err_console = Console(stderr=True, style="red")


# ---------------------------------------------------------------- subcommands

members_app = typer.Typer(help="Member directory operations.", no_args_is_help=True)
companies_app = typer.Typer(help="Corporate (company) membership operations.", no_args_is_help=True)
events_app = typer.Typer(help="Event operations.", no_args_is_help=True)

app.add_typer(members_app, name="members")
app.add_typer(companies_app, name="companies")
app.add_typer(events_app, name="events")


# ---------------------------------------------------------------- helpers

def _unwrap(response: dict):
    """Glue Up sometimes wraps the payload in `data`, sometimes not. Return inner."""
    if isinstance(response.get("data"), dict):
        return response["data"]
    return response


def _client() -> GlueUpClient:
    try:
        return GlueUpClient()
    except GlueUpError as e:
        err_console.print(f"Config error: {e}")
        err_console.print("Make sure .env is present (see .env.example).")
        raise typer.Exit(2)


def _emit(value, json_mode: bool) -> None:
    if json_mode:
        console.print_json(data=value)


def _print_records_table(records: list, columns: list[tuple[str, str]], title: str | None = None):
    """Render a list of dicts as a rich table.

    `columns` is a list of (header, dotted.path) tuples.
    """
    table = Table(title=title, show_lines=False, header_style="bold cyan")
    for header, _ in columns:
        table.add_column(header)
    for rec in records:
        row = []
        for _, path in columns:
            row.append(_dotted_get(rec, path))
        table.add_row(*row)
    console.print(table)


def _dotted_get(obj, path: str) -> str:
    cur = obj
    for part in path.split("."):
        if cur is None:
            return ""
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return ""
    if cur is None:
        return ""
    if isinstance(cur, (dict, list)):
        return _json.dumps(cur, ensure_ascii=False, default=str)
    return str(cur)


# ---------------------------------------------------------------- root cmds

@app.command()
def whoami(
    json: bool = typer.Option(False, "--json", help="Output raw JSON."),
):
    """Show the current API account / tenant / org config."""
    c = _client()
    data = {
        "public_key": c.config.public_key,
        "tenant_id": c.config.tenant_id,
        "org_id": c.config.org_id,
        "base_url": c.config.base_url,
    }
    if json:
        console.print_json(data=data)
        return
    table = Table(show_header=False, box=None)
    for k, v in data.items():
        table.add_row(k, str(v))
    console.print(table)


@app.command("auth-check")
def auth_check():
    """Hit a no-token endpoint to verify credentials work."""
    c = _client()
    try:
        c.get("membershipDirectory/settings")
        console.print(f"[green]✓[/green] Auth OK — base [bold]{c.config.base_url}[/bold]")
    except GlueUpError as e:
        err_console.print(f"✗ Auth FAILED: {e}")
        raise typer.Exit(1)


@app.command()
def settings(json: bool = typer.Option(False, "--json")):
    """Show the membership directory settings (visibility, search filters)."""
    c = _client()
    r = _unwrap(c.get("membershipDirectory/settings"))
    value = r.get("value", {})
    if json:
        console.print_json(data=value)
        return
    vis = value.get("visibility", {})
    console.print(f"[bold]Directory visibility[/bold]: {vis}")
    console.print(
        f"Individual fields: {len(value.get('individualFieldsVisibility', []))} configured. "
        f"Corporate fields: {len(value.get('corporateFieldsVisibility', []))} configured."
    )
    console.print(f"Corporate search filters: {value.get('corporateSearchFilters')}")
    console.print(f"Individual search filters: {value.get('individualSearchFilters')}")


# ---------------------------------------------------------------- members

MEMBER_COLUMNS = [
    ("ID", "individualMember.id"),
    ("Name", "individualMember.givenName"),
    ("Family", "individualMember.familyName"),
    ("Email", "individualMember.emailAddress.value"),
    ("Type", "membership.membershipType.title"),
    ("Primary", "individualMember.primary"),
]


@members_app.command("list")
def members_list(
    limit: int = typer.Option(20, "--limit", "-n", help="Page size."),
    offset: int = typer.Option(0, "--offset"),
    search: Optional[str] = typer.Option(None, "--search", "-s",
        help="Free-text search across name + email."),
    json: bool = typer.Option(False, "--json"),
):
    """List members from the directory."""
    c = _client()
    body: dict = {"projection": [], "offset": offset, "limit": limit}
    if search:
        body["search"] = {
            "fields": ["givenName", "familyName", "emailAddress"],
            "value": search, "fullText": True,
        }
    r = _unwrap(c.post("membershipDirectory/members", json=body))
    value = r.get("value") or []
    total = ((r.get("metadata") or {}).get("pagination") or {}).get("total")
    if json:
        console.print_json(data={"total": total, "value": value})
        return
    _print_records_table(value, MEMBER_COLUMNS, title=f"Members ({offset}–{offset+len(value)} of {total})")


@members_app.command("get")
def members_get(
    member_id: int = typer.Argument(..., help="Individual member ID."),
    json: bool = typer.Option(False, "--json"),
):
    """Fetch one member by ID."""
    c = _client()
    r = _unwrap(c.get(f"membershipDirectory/member/{member_id}"))
    value = r.get("value") or {}
    if json:
        console.print_json(data=value)
        return
    console.print_json(data=value)  # rich's pretty JSON for a single record


# ---------------------------------------------------------------- companies

COMPANY_COLUMNS = [
    ("ID", "id"),
    ("Name", "name"),
    ("Type", "membershipType.title"),
    ("Country", "address.country.code"),
    ("Website", "companyWebsiteAddress"),
    ("Members", "members"),  # will print as JSON via _dotted_get
]


@companies_app.command("list")
def companies_list(
    limit: int = typer.Option(20, "--limit", "-n"),
    offset: int = typer.Option(0, "--offset"),
    search: Optional[str] = typer.Option(None, "--search", "-s"),
    basic: bool = typer.Option(False, "--basic", help="Use lighter /basic endpoint."),
    json: bool = typer.Option(False, "--json"),
):
    """List corporate (company) memberships."""
    c = _client()
    path = "membershipDirectory/corporateMemberships" + ("/basic" if basic else "")
    body: dict = {"projection": [], "offset": offset, "limit": limit}
    if search:
        body["search"] = {"fields": ["name"], "value": search, "fullText": True}
    r = _unwrap(c.post(path, json=body))
    value = r.get("value") or []
    total = ((r.get("metadata") or {}).get("pagination") or {}).get("total")
    if json:
        console.print_json(data={"total": total, "value": value})
        return
    # for the table, compress members[] to a count
    for v in value:
        if isinstance(v.get("members"), list):
            v["members"] = f"{len(v['members'])}"
    _print_records_table(value, COMPANY_COLUMNS, title=f"Companies ({offset}–{offset+len(value)} of {total})")


@companies_app.command("get")
def companies_get(
    company_id: int = typer.Argument(...),
    json: bool = typer.Option(False, "--json"),
):
    """Fetch one company membership."""
    c = _client()
    r = _unwrap(c.get(f"membershipDirectory/corporate/{company_id}"))
    console.print_json(data=r.get("value") or {})


# ---------------------------------------------------------------- events

EVENT_COLUMNS = [
    ("ID", "id"),
    ("Title", "title"),
    ("Start", "startDateTime"),
    ("Type", "eventType.name"),
    ("Published", "published"),
]


@events_app.command("list")
def events_list(
    limit: int = typer.Option(20, "--limit", "-n"),
    json: bool = typer.Option(False, "--json"),
):
    """List events."""
    c = _client()
    body = {
        "projection": ["id", "title", "startDateTime", "endDateTime",
                       "eventType.code", "eventType.name", "published",
                       "eventTag", "workingGroup"],
        "filter": [], "offset": 0, "limit": limit,
        "order": {"startDateTime": "desc"},
    }
    r = _unwrap(c.post("event/list", json=body))
    value = r.get("value") or []
    total = ((r.get("metadata") or {}).get("pagination") or {}).get("total")
    if json:
        console.print_json(data={"total": total, "value": value})
        return
    _print_records_table(value, EVENT_COLUMNS, title=f"Events ({len(value)} of {total})")


ATTENDEE_COLUMNS = [
    ("ID", "id"),
    ("First name", "givenName"),
    ("Last name", "familyName"),
    ("Email", "emailAddress.value"),
    ("Company", "companyName"),
    ("Status", "approvalStatus"),
]

ATTENDEE_FORM_COLUMNS = [
    ("ID", "id"),
    ("Custom", "isCustom"),
    ("Template", "isTemplate"),
    ("Fields", "fields"),
]


@events_app.command("attendees")
def events_attendees(
    event_id: int = typer.Argument(..., help="Glue Up event ID."),
    limit: int = typer.Option(100, "--limit", "-n"),
    json: bool = typer.Option(False, "--json"),
):
    """List attendees for an event."""
    c = _client()
    body = {
        "projection": ["id", "givenName", "familyName", "emailAddress",
                       "companyName", "positionTitle", "phoneNumber",
                       "approvalStatus"],
        "offset": 0,
        "limit": limit,
    }
    r = _unwrap(c.post(f"event/{event_id}/attendeeList", json=body))
    value = r.get("value") or []
    total = ((r.get("metadata") or {}).get("pagination") or {}).get("total")
    if json:
        console.print_json(data={"total": total, "value": value})
        return
    _print_records_table(value, ATTENDEE_COLUMNS, title=f"Attendees for event {event_id} ({len(value)} of {total})")


@events_app.command("attendee-forms")
def events_attendee_forms(
    event_id: int = typer.Argument(..., help="Glue Up event ID."),
    json: bool = typer.Option(False, "--json"),
):
    """List attendee registration forms for an event."""
    c = _client()
    body = {"offset": 0, "limit": 100, "projection": []}
    r = _unwrap(c.post(f"event/{event_id}/attendeeForm", json=body))
    value = r.get("value") or []
    total = ((r.get("metadata") or {}).get("pagination") or {}).get("total")
    if json:
        console.print_json(data={"total": total, "value": value})
        return
    # Summarise: show one row per form with field count
    rows = [
        {**f, "fields": str(len(f.get("fields") or []))}
        for f in value
    ]
    _print_records_table(rows, ATTENDEE_FORM_COLUMNS, title=f"Attendee forms for event {event_id} ({len(value)} of {total})")


@events_app.command("attendee-form")
def events_attendee_form(
    event_id: int = typer.Argument(..., help="Glue Up event ID."),
    form_id: str = typer.Argument(..., help="Attendee form ID."),
    json: bool = typer.Option(False, "--json"),
):
    """Retrieve a specific attendee registration form by ID."""
    c = _client()
    r = _unwrap(c.get(f"event/{event_id}/attendeeForm/{form_id}"))
    value = r.get("value") or {}
    if json:
        console.print_json(data=value)
        return
    console.print_json(data=value)


@events_app.command("attendee-form-fields")
def events_attendee_form_fields(
    event_id: int = typer.Argument(..., help="Glue Up event ID."),
    json: bool = typer.Option(False, "--json"),
):
    """List all attendee form fields for an event."""
    c = _client()
    r = _unwrap(c.get(f"event/{event_id}/attendeeFormFields"))
    value = r.get("value") or []
    if json:
        console.print_json(data=value)
        return
    cols = [("ID", "id"), ("Key", "key"), ("Type", "type"), ("Default", "isDefault")]
    _print_records_table(value, cols, title=f"Attendee form fields for event {event_id}")


# ---------------------------------------------------------------- raw

@app.command()
def raw(
    method: str = typer.Argument(..., help="GET / POST / PUT / DELETE"),
    path: str = typer.Argument(..., help="Endpoint path, e.g. membershipDirectory/settings"),
    body: Optional[str] = typer.Option(None, "--body", "-b",
        help="JSON body (use '-' to read from stdin)."),
):
    """Make a raw API call. Prints JSON. Useful for poking at undocumented endpoints."""
    c = _client()
    payload = None
    if body == "-":
        payload = _json.load(sys.stdin)
    elif body:
        payload = _json.loads(body)
    try:
        r = c.request(method.upper(), path, json=payload)
        console.print_json(data=r)
    except GlueUpError as e:
        err_console.print(f"✗ {e}")
        if e.payload:
            console.print_json(data=e.payload)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
