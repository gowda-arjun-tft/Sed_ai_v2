# Install Railway Track

## 2026-09-07 10:38 IST

**User**

Install the repository-scoped Railway Track skill from its canonical raw GitHub source after resolving `main` to an immutable commit, validating collisions and provenance, initializing the minimum records, and reporting discovery separately from activation.

**Agent**

Completed: Installed the commit-pinned Railway Track skill at `.agents/skills/railway-track/SKILL.md` and initialized the minimum repository records. The requested `main` ref resolved to `93603d145a43503b4457fc5ef237d12850d910aa`; the installed file SHA-256 is `1d9fcc22eea8f43ff3ffa83ae740f1c3458997c0cb5f1a85dabe365391249e08`. Current-session discovery remains unverified because this host exposed no skill-catalog refresh tool; no instruction bridge was added.

**Verification**

Fetched and installed bytes are identical. YAML frontmatter parsed, the name is `railway-track`, the parent-directory contract passed, every required path exists inside the repository without a symlink escape, no duplicate skill was found in the effective locations inspected, and `git diff --check -- .agents railway-track` passed. Invocation and automatic activation were not tested.
