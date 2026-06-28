# isaca

A small MCP (Model Context Protocol) server exposing ISACA-related reference
tools over an SSE/JSON-RPC interface (`main.py`).

## Tools

### `about_isaca`
Returns detailed information about ISACA — who they are, what they do, their
certifications, membership, and mission. No inputs.

### `about_cisa`
Returns detailed information about the CISA (Certified Information Systems
Auditor) certification — exam details, eligibility, syllabus, and benefits.
No inputs.

### `generate_audit_checklist`
Returns ISACA-aligned IT audit steps for a given control domain. For
educational use.

**Inputs**

| Name     | Type   | Required | Description                                            |
| -------- | ------ | -------- | ------------------------------------------------------ |
| `domain` | string | yes      | Control domain, e.g. `"cloud security"`, `"access management"`. |

**Behaviour**

- The input is normalized (lowercased, trimmed, whitespace collapsed) and
  matched to a known domain using keyword/alias matching (not exact-string
  only). For example `cloud`, `csp`, `saas`, `iaas`, and `paas` all resolve to
  **cloud security**.
- Known domains: `cloud security`, `access management`, `data privacy`,
  `network security`.
- If no domain matches, a **general** fallback checklist is returned and the
  response `matched` flag is set to `false`.

**Output** (JSON in the text content)

```json
{
  "domain": "cloud security",
  "requested_domain": "Cloud Security",
  "matched": true,
  "steps": [
    { "step": "Cloud governance & strategy", "objective": "Verify cloud adoption aligns with governance, risk appetite, and documented strategy." }
  ],
  "note": "This checklist is illustrative and ISACA-aligned but should be tailored ..."
}
```

Every response carries an educational disclaimer in `note`: the checklist is
illustrative and ISACA-aligned but should be tailored to the engagement's
scope. An invalid or empty `domain` returns an `error` message instead.

The checklist content, domain aliases, and disclaimer are stored in
`isaca_data/audit_checklists.json` (alongside the other tools' data files),
so they can be edited without touching `main.py`.

## Running

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
