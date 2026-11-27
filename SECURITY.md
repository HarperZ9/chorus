# Security Policy

## Supported versions

`chorus-discourse` is distributed on PyPI and packaged as a local discourse analyzer CLI and stdio
MCP server. Security fixes ship in the current release line as a new release. Older lines do not
receive backports.

| Version | Supported |
|-|-|
| 0.3.x | Yes |
| < 0.3 | No |

## Reporting a vulnerability

Report suspected vulnerabilities privately through GitHub: open this repository's **Security** tab
and select **Report a vulnerability**, or open
<https://github.com/HarperZ9/chorus/security/advisories/new>.
Keep security reports out of public issues, pull requests, and discussions.

Include:

- the affected version and operating system,
- a concise description of the issue and its impact,
- the minimal input or steps needed to reproduce it.

The maintainer, Zain Dana Harper, acknowledges reports and works on a fix before public disclosure.
Allow a reasonable period to remediate before disclosing.

## Scope and trust model

Chorus analyzes comment sections and discourse corpora locally without calling external models, and
emits deterministic receipts that anyone can re-run.

- **Local execution, zero default network.** Core clustering, sentiment scoring, and receipt
  verification run offline with no telemetry and no model API calls.
- **Untrusted comment inputs.** Exported comment threads, JSON, CSV, and text files may contain
  untrusted user-authored content. Chorus parses all comment fields strictly as data.
- **MCP surface.** The MCP server communicates over stdio JSON-RPC and binds no network port. Tool
  outputs return to the connected MCP client and its configured provider.
- **What counts as a vulnerability.** Code execution from malicious comment payloads, path traversal
  writing outside explicitly specified output locations, or a tampered discourse receipt that still
  verifies as valid.
- **What does not count.** Disagreement over topic cluster boundaries or sentiment weights on
  ambiguous text, or malformed inputs rejected with a normal error.

## Good practice

- Strip personal identifiers from comment datasets before sharing exported reports or receipts.
- Treat raw comment archives as untrusted data when chaining downstream tools.
