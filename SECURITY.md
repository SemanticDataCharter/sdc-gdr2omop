# Security

Report a vulnerability privately to security@axius-sdc.com, or through GitHub's private vulnerability reporting
(Security tab, "Report a vulnerability"). Please do not open a public issue. The organization
policy is at https://github.com/SemanticDataCharter/.github/blob/main/SECURITY.md. Expect an acknowledgement within
three business days, and a fix released before anything is made public.

## Supported versions

| version | supported |
|---|---|
| 4.0.x | yes |

## What counts as a vulnerability here

This package is a target mapper for `sdc-mapper`: it writes a Governed Data Record as the OMOP Common Data Model 5.4 and reports what it did
with every value. A value written without being reported, reported in the wrong class (lookup, declared, carried,
not representable), or an Exceptional Value reported as preserved when it was degraded or lost, is an integrity
defect and in scope. So is output that claims conformance to the OMOP Common Data Model 5.4 and does not conform.

The package has no command line and no server of its own; it runs inside `sdc-mapper`, whose SECURITY.md covers
the MCP server. It makes no network requests.

Out of scope: the authenticity of a record or mapping file the caller supplies.
