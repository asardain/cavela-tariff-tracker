# Cavela Tariff Tracker — Reliability Ontology

## Overview

Every claim extracted by the tariff tracker is assigned a certainty level from 1 to 7. This ontology defines what each level means, what linguistic or contextual signals indicate it, and what sources can produce claims at each level.

The higher the level, the more certain the claim is — the more official, verifiable, and final the action described.

---

## Levels

### Level 1 — SPECULATION

**Definition**: The claim is based on analyst opinion, unnamed sources, or speculative language. The action described has not been confirmed by any official or named source.

**Signal phrases**: "could", "might", "may", "considering", "thinking about", "mulling", "possible", "might impose", "analysts say", "sources say" (unnamed), "market participants expect"

**Typical sources**: Financial commentary, op-eds, analyst notes, unnamed-source reporting

**Source reliability floor**: News wires and financial press can produce Level 1 claims. Official government sources cannot (government sources floor at Level 3).

**Example**: "The White House is reportedly considering a 25% tariff on Canadian steel imports."

---

### Level 2 — REPORTED

**Definition**: The claim is based on named sources, official-adjacent reporting, or strong news reporting with attribution. The action is described as planned or expected but not officially announced.

**Signal phrases**: "plans to", "is expected to", "will announce", "intends to", "has told reporters", "according to [named official]", "is preparing to"

**Typical sources**: Reuters, Bloomberg, WSJ, Politico with named-source attribution

**Source reliability floor**: News wires and financial press.

**Example**: "According to three people familiar with the matter, the Biden administration plans to impose tariffs on solar panel imports from Southeast Asia."

---

### Level 3 — PROPOSED

**Definition**: An official government body has formally proposed the action through a regulatory mechanism. A public comment period has been opened, or an NPRM (Notice of Proposed Rulemaking) has been filed.

**Signal phrases**: "proposed rule", "NPRM", "notice of proposed rulemaking", "public comment period", "proposed tariff", "seeks public comment", "proposes to"

**Typical sources**: Federal Register, USTR, USITC, CBP official documents

**Source reliability floor**: Official US government sources (level 3 minimum).

**Example**: "The Department of Commerce published an NPRM proposing anti-dumping duties on aluminum extrusions from China, with a 30-day public comment period."

---

### Level 4 — ANNOUNCED

**Definition**: An official announcement has been made by the relevant government agency or administration official. This includes press releases, official statements, and confirmed policy announcements — but not yet signed into law or published as final rule.

**Signal phrases**: "announced today", "the administration announced", "USTR announced", "CBP announced", "in a press release", "confirmed by", "official statement"

**Typical sources**: USTR press releases, White House press briefings, CBP announcements, agency press releases

**Source reliability floor**: Any source can report an announcement, but the announcement itself must be from an official body.

**Example**: "The USTR announced a 15% tariff on electric vehicles imported from China, effective March 1, 2025."

---

### Level 5 — EXECUTIVE_ORDER

**Definition**: A Presidential Executive Order or Presidential Proclamation has been signed that establishes or modifies tariff policy. This carries the force of executive authority and is immediately or imminently effective.

**Signal phrases**: "executive order", "presidential proclamation", "signed by the president", "EO [number]", "proclamation [number]", "by authority of the president"

**Typical sources**: Federal Register (EO publication), White House press releases, official presidential proclamations

**Source reliability floor**: Must reference a specific EO or Proclamation number or text.

**Example**: "President Biden signed Executive Order 14074 imposing a 100% tariff on legacy semiconductor chips imported from China."

---

### Level 6 — RULE_PUBLISHED

**Definition**: A final rule has been published in the Federal Register. This is the regulatory completion of a proposed rule — it has gone through public comment, been finalized, and is now binding law at the regulatory level.

**Signal phrases**: "final rule", "published in the Federal Register", "effective [date]", "amending 19 CFR", "final determination", "Federal Register Vol. [X]"

**Typical sources**: Federal Register, CBP, USTR official regulatory documents

**Source reliability floor**: Must reference Federal Register publication.

**Example**: "CBP published a final rule in the Federal Register (Vol. 89, No. 45) establishing new procedures for tariff classification of electric vehicle batteries, effective April 15, 2025."

---

### Level 7 — LAW

**Definition**: An Act of Congress has been signed into law that establishes, modifies, or removes tariff policy. This is the highest level of certainty — it represents enacted legislation.

**Signal phrases**: "signed into law", "Public Law [number]", "enacted", "Act of [year]", "Congress passed", "the President signed"

**Typical sources**: Congress.gov, White House signing statements, Federal Register

**Source reliability floor**: Must reference a specific Public Law number or Congressional record.

**Example**: "The Bipartisan Trade Clarity Act (Public Law 118-xxx) was signed into law, establishing permanent normal trade relations with Vietnam and removing remaining MFN tariffs."

---

## Source Category Floors

| Source Category | Minimum Certainty Level |
|----------------|------------------------|
| `official_us_gov` | 3 (PROPOSED) |
| `international_body` | 2 (REPORTED) |
| `news_wire` | 1 (SPECULATION) |
| `financial_press` | 1 (SPECULATION) |

The floor means: a claim sourced from an official US government outlet cannot be classified below Level 3, even if the language used is speculative. If official language is used speculatively, it should still be raised to Level 3 minimum.

---

## Classification Algorithm

1. Start with the linguistic signals in the claim text to determine a base level (1–7)
2. Apply the source category floor (raise to floor if below it)
3. Write a one-sentence rationale explaining the classification
4. Return: `certainty_level` (int), `certainty_label` (str), `certainty_rationale` (str)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-05 | Initial ontology definition |
