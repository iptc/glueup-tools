"""Walk the Glue Up member directory and normalise individual members."""

from __future__ import annotations

from dataclasses import dataclass

from .client import GlueUpClient


@dataclass
class GlueUpMember:
    """Normalised view of an individual member, drawn from Glue Up directory rows."""

    email: str            # lowercased; the join key
    given_name: str
    family_name: str
    company: str
    membership_type: str  # used as a Mailchimp tag

    @classmethod
    def from_directory_row(cls, row: dict) -> "GlueUpMember | None":
        ind = row.get("individualMember") or {}
        email = ((ind.get("emailAddress") or {}).get("value") or "").strip().lower()
        if not email or "@" not in email:
            return None
        return cls(
            email=email,
            given_name=(ind.get("givenName") or "").strip(),
            family_name=(ind.get("familyName") or "").strip(),
            company=(ind.get("companyName") or "").strip(),
            membership_type=(((row.get("membership") or {}).get("membershipType") or {}).get("title") or "").strip(),
        )


class _MemberList(list):
    """A list that can carry diagnostic attributes (skipped counts etc.)."""
    skipped_no_email: int = 0


def fetch_all_glueup_members(client: GlueUpClient, *, page_size: int = 100) -> _MemberList:
    """Walk the entire Glue Up member directory, returning normalised individuals."""
    out = _MemberList()
    skipped = 0
    offset = 0
    while True:
        body = client.post(
            "membershipDirectory/members",
            json={"projection": [], "offset": offset, "limit": page_size},
        )
        data = body.get("data", body)
        rows = data.get("value") or []
        total = ((data.get("metadata") or {}).get("pagination") or {}).get("total") or 0
        for row in rows:
            m = GlueUpMember.from_directory_row(row)
            if m is None:
                skipped += 1
            else:
                out.append(m)
        if not rows or offset + len(rows) >= total:
            break
        offset += len(rows)
    out.skipped_no_email = skipped
    return out
