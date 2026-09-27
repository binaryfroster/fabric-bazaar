# Workflow Specification: Continuous AI-Generated Code Security Auditor

## Overview
An automated, event-driven security audit workflow designed to catch AI scaffolding failure modes, multi-tenant authorization lapses (BOLA/IDOR), credential leaks, and data exposure in the repository before code reaches production.

---

## 1. Trigger
- **Pre-Push Event (Local Developer Loop):**
  - Git pre-push hook runs a lightweight static security scan on all staged and modified files.
  - Command: `python scripts/security_audit_scanner.py --staged`
- **Pull Request & Main Branch Push (CI/CD Pipeline):**
  - GitHub Actions workflow (`.github/workflows/security-audit.yml`) triggers on every PR targeting `main` and on direct commits to `main`.

---

## 2. Scan Scope (Full Spectrum)
The auditor executes heuristic and AST-based scans across the following vectors:
1. **Secrets & Credentials (CWE-798):**
   - High-entropy tokens, private keys, `DATABASE_URL` with hardcoded credentials, unmasked third-party API keys (Razorpay, OpenAI, Stripe, S3).
   - Distinction between client-exposed prefixes (`NEXT_PUBLIC_`, `VITE_`, `PUBLIC_`) and server-only environment variables.
2. **Multi-Tenant Access Control & IDOR (CWE-862, CWE-639):**
   - Verification that seller, buyer, and delivery mutations explicitly filter by tenant identity (e.g. `company_id == comp.id` or `user_id == current_user.id`) rather than raw primary key lookup (`get_or_404(id)`).
3. **Public API & PII Exposure (CWE-200, CWE-359):**
   - Verification that unauthenticated public routes (tracking, lookup, webhooks) mask names, emails, phone numbers, and physical street addresses.
4. **Transport & Cookie Flags (CWE-614, CWE-1004):**
   - `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SECURE = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`, security headers (`HSTS`, `X-Content-Type-Options`, `CSP`).
5. **Prompt Injection & Excessive Agency (CWE-1426, OWASP LLM01, LLM06):**
   - Untrusted request inputs concatenated into system prompts or model instructions wired to executable tools.

---

## 3. Push Right Architecture
To minimize developer cognitive load, the workflow pushes human involvement as far right as possible:
1. **Detection:** Scans code and maps every issue to a CWE and specific file/line location.
2. **Automated Remediator:** If vulnerabilities are found, the auditor automatically generates the minimal, non-breaking one-commit patch.
3. **Branch Staging:** Branches off as `security/audit-fix-<timestamp>` and commits the patch cleanly.
4. **Verification:** Runs unit tests and syntax checks (`py_compile`) against the patched branch to ensure zero regressions.

---

## 4. Checkpoint (Human-in-the-Loop)
The developer is presented with a **Decision-Ready Brief** — never a wall of raw scanner logs.

### Brief Format
```markdown
### 🛡️ Security Audit Brief: [Repository/Branch]
- **Status:** [Vulnerabilities Found & Patched | Clean]
- **Findings Count:** [Critical: X | High: Y | Medium: Z]

#### Proposed Fix Patch:
1. [SEVERITY] [Vulnerability Name] — [file:line] ([CWE-XXX])
   • Exploit: [Exact attack scenario]
   • Fix Applied: [One-line summary of code change]

- **Branch with Staged Patch:** `security/audit-fix-YYYYMMDD`
- **Action:** [1-Click Merge / Review PR / Reject]
```

---

## 5. Implementer Instructions
Any AI or CI worker executing this workflow must:
1. Run static checks locally or in ephemeral CI containers without sending proprietary source code to external third-party telemetry services.
2. Reject false comfort: report findings worst-first with line numbers, proof-of-concept exploits, and concrete fixes.
3. Never silently modify the `main` branch without a pull request or developer review brief.
