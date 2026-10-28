"""Python client and command-line tool for the Glue Up open API v2.

See https://glueupapi.docs.apiary.io/ for the upstream docs.
"""

from .client import GlueUpClient, GlueUpError
from .members import GlueUpMember, fetch_all_glueup_members

__all__ = ["GlueUpClient", "GlueUpError", "GlueUpMember", "fetch_all_glueup_members"]
__version__ = "0.2.0"
