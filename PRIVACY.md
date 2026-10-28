[🇬🇧 English](PRIVACY.md) | [🇷🇺 Русский](PRIVACY.ru.md)

# Privacy Policy — Amagi-Player

| Field | Value |
|---|---|
| Document | Privacy Policy (Data Protection Notice) |
| Version | 2.0 |
| Effective date | 2026-01-01 (rev. 2026-10-28) |
| Applies to | Amagi-Player, all platforms, all distribution channels |
| Language of record | English |
| Status | active |

---

## 0. Document control

This document is the privacy policy (Data Protection Notice) of the Amagi-Player
software and is published in the project repository. The current version is
available at `https://github.com/AkashaForge/ama-gi-player/blob/main/PRIVACY.md`.

The document follows the layered-notice model recommended by Art. 12(7) GDPR
and equivalent data-protection regimes: a short summary, an overview table,
the full text, and technical annexes. All layers form a single document and
do not contradict each other.

This Policy has been drafted with reference to:

- **European Union**: General Data Protection Regulation (GDPR), 2016/679;
- **United States**: COPPA (15 U.S.C. §§ 6501–6506); California Consumer
  Privacy Act as amended by CPRA (Cal. Civ. Code § 1798.100 et seq.);
  Virginia Consumer Data Protection Act (Va. Code § 59.1 et seq.); Colorado
  Privacy Act (C.R.S. § 6-1-1301 et seq.); Connecticut Data Privacy Act
  (Conn. Gen. Stat. § 42-515 et seq.);
- **Russian Federation**: Federal Law No. 152-FZ of 27.07.2006
  "On Personal Data" (as amended).

Because the Application processes no personal data on Developer-controlled
infrastructure (see §3), none of the above regimes imposes obligations on the
Developer; references are provided for transparency and to describe how the
rights of the User are exercised locally.

---

## 1. Definitions

**1.1. "Application"** — the Amagi-Player software distributed under the
GNU GPL v3.0 license, including source code, executables, configuration
files, and documentation.

**1.2. "Developer"** — the natural or legal person developing and publishing
the Application (AkashaForge). The Developer is not a controller or operator
of the User's personal data within the meaning of any applicable law.

**1.3. "User"** — a natural person using the Application on their own device.

**1.4. "Device"** — the hardware of the User on which the Application is
installed and operates.

**1.5. "Source"** — an external network service that the Application contacts
to obtain content or metadata (Internet Archive, Kinopoisk API, user-defined
sources, local external indexers).

**1.6. "Personal data"** — information relating to an identified or
identifiable natural person, within the meaning of Art. 4(1) GDPR, Art. 3(1)
152-FZ, and equivalent norms.

**1.7. "Processing"** — any operation on personal data, including collection,
recording, storage, modification, retrieval, use, transfer, and erasure.

**1.8. "Local data"** — data created and stored by the Application exclusively
on the User's Device, under the User's sole control.

---

## 2. Scope

**2.1. Within the scope of this Policy:**

- processing of Local data by the Application on the User's Device;
- network requests initiated by the Application;
- configuration files created or modified by the User
  (`data/mode.txt`, `data/sources.txt`, `.env`);
- diagnostic console output produced by the Application.

**2.2. Outside the scope of this Policy:**

- processing of data by the Device's operating system;
- processing of data by Sources (governed by the respective Source's policies);
- processing of data by third-party programs installed by the User;
- processing of data on GitHub's side in connection with the project
  repository.

---

## 3. Roles and responsibilities

**3.1.** The Developer **does not act** as a controller, processor, or
operator of the User's personal data, because:

- the Developer does not receive the User's personal data;
- the Developer has no technical means of accessing the User's Device;
- the Developer does not process personal data on behalf of, or under the
  instruction of, the User.

**3.2.** The User is the sole party controlling the processing of Local data
on their Device. Under 152-FZ, the User is the operator of any personal data
contained in `.env` (if an API key is present).

**3.3.** The User's interaction with Sources is governed by the policies of
the respective Sources. The Developer is not a party to those relationships.

---

## 4. Lawful basis and principles

**4.1.** Processing of Local data is carried out by the Application solely
for its own operation, on the basis of the User's consent given on first
launch (Art. 6(1)(a) GDPR; Art. 9 152-FZ), and for performance of the
agreement on use of the Application (Art. 6(1)(b) GDPR).

**4.2.** The Application adheres to the principles of:

- **minimization** (Art. 5(1)(c) GDPR; Art. 5 152-FZ) — only the strict
  minimum of data is processed;
- **storage limitation** (Art. 5(1)(e) GDPR) — data is stored until the User
  deletes it;
- **transparency** (Art. 5(1)(a) GDPR; Art. 18 152-FZ) — this Policy
  describes every category of data;
- **integrity and confidentiality** (Art. 5(1)(f) GDPR) — data does not
  leave the User's Device (with the sole exception of network requests,
  see §7);
- **accountability** (Art. 5(2) GDPR) — this document records the
  architectural decisions that preclude processing of personal data by the
  Developer.

**4.3.** Because the Developer does not process personal data, obligations
under Art. 30 GDPR (records of processing activities) and Art. 22 152-FZ
(notification to Roskomnadzor) do not apply to the Developer.

---

## 5. Categories of processed data

**5.1.** The Application processes the following categories of Local data.

| # | Category | Format | Location | Purpose | Retention |
|---|---|---|---|---|---|
| 1 | Watch history | SQLite | `data/app_data.db` (table `user_history`) | "Continue watching" | until deleted by User |
| 2 | Poster cache | JPEG/PNG | `data/cache/{kp_id}.jpg` | UI performance | until deleted by User |
| 3 | Metadata cache | JSON | `data/cache/short/{id}.json`, `data/cache/full/{id}.json`, `data/cache/lists/{hash}.json` | reduce network requests | until deleted by User |
| 4 | Film catalog | SQLite | `data/whitelist.db` (derived from bundled `data/whitelist_seed.db`) | feed of public-domain films | bundled with Application; recreated from seed |
| 5 | Mode selection | plain text | `data/mode.txt` | mode choice (`public` / `private`) | until deleted by User |
| 6 | Source list | plain text | `data/sources.txt` | user-defined content sources | until file is deleted |
| 7 | API keys | plain text | `.env` (next to executable) | optional access to Kinopoisk API | until deleted by User |
| 8 | Diagnostic output | plain text (console) | stderr (not persisted) | diagnostics | not stored |

**5.2.** No category from §5.1 is transmitted to the Developer or to third
parties on the Developer's behalf.

**5.3.** `config.py` is a **read-only source-code module** containing default
parameters (paths, timeouts, feature flags). It is not a data store and
contains no User data. User-specific settings live only in `.env` and the
`data/*.txt` files listed above.

**5.4.** Full technical specifications are in Annex A.

---

## 6. Categories NOT processed

**6.1.** The Application does not process the following categories:

| # | Category | Processed |
|---|---|---|
| 1 | Name, surname, email, phone, postal address | **no** |
| 2 | Credentials (logins, passwords, access tokens) | **partial** — see §6.2 |
| 3 | Payment information | no |
| 4 | Biometric data | no |
| 5 | Geolocation (GPS, IP geolocation) | no |
| 6 | Contacts, files, messages from the Device | no |
| 7 | Usage analytics | no |
| 8 | Telemetry, crash reports | no |
| 9 | Advertising identifiers | no |
| 10 | Fingerprinting data (canvas, fonts, WebGL) | no |

**6.2. API key (exception to #2).** An optional Kinopoisk API key may be stored
in `.env` at the User's discretion. It is not a credential for any account
held by the Developer; it identifies the User only to the Kinopoisk API
(`kinopoiskapiunofficial.tech`) and is transmitted only to that service and
only when the User triggers a metadata request. In `public` mode the
Kinopoisk API is **not called** by the Application. The Developer never
receives this key.

**6.3.** The Application contains no analytics, advertising, telemetry,
crash-reporting, or A/B-testing modules.

---

## 7. Network interactions

**7.1.** The Application initiates network requests solely to obtain content
and metadata from Sources chosen by the User.

**7.2.** Typical network interactions:

| # | Recipient | Trigger | Data transmitted |
|---|---|---|---|
| 1 | Internet Archive (`archive.org`) | search, playback | IP address, User-Agent, HTTP headers, search query |
| 2 | Kinopoisk API (`kinopoiskapiunofficial.tech`) | optional, only if `KP_API_KEY` is set **and** `private` mode | IP address, User-Agent, API key, film identifier |
| 3 | User-defined sources (`data/sources.txt`) | if added by User | IP address, User-Agent, HTTP headers, search query |
| 4 | Local external indexer (e.g. Jackett at `localhost`) | if installed by User | HTTP request over loopback |
| 5 | BitTorrent swarms of Internet Archive | playback in `private` mode only | IP address, port, BitTorrent peer-id |

**7.3.** Transmission of IP address, User-Agent, and HTTP headers is an
inherent property of the HTTP protocol and is not the result of any data
collection by the Developer.

**7.4.** The Developer does not control data processing by Sources and is
not responsible for such processing. Each Source's privacy policy is
determined by that Source.

**7.5.** Users for whom additional privacy during network interactions
matters may apply standard operating-system or network-layer tools at their
own discretion. The Application neither requires nor configures such tools
automatically.

**7.6.** Full specification of endpoints is provided in Annex B.

---

## 8. Third parties and sub-processors

**8.1.** The Developer does not engage processors or sub-processors to
process the User's personal data.

**8.2.** The Developer does not transfer Local data to third parties.

**8.3.** The Developer does not perform any international transfer of the
User's personal data, because it does not receive such data.

---

## 9. Retention

**9.1.** The retention period for Local data is unlimited and is determined
solely by the User.

**9.2.** Local data is erased:

- through Application settings (cleanup function);
- manually — by deleting the corresponding files and folders;
- when the Application is removed from the Device.

**9.3.** Once deleted, Local data cannot be restored by the Application's
own means.

---

## 10. Security measures

**10.1.** The Application applies the following protections for Local data:

- no network transmission of Local data to the Developer's servers;
- no remote access to the User's Device by the Developer;
- isolation of child processes (FFmpeg, headless browser) with lifetime
  control;
- no built-in remote-control mechanisms.

**10.2.** Protection of the Device at the operating-system level (disk
encryption, user privilege separation, antivirus protection) is the User's
responsibility.

**10.3.** Because the Developer does not process personal data, obligations
under Art. 32 GDPR (security of processing) and Art. 19 152-FZ (measures to
ensure security) do not apply to the Developer. The measures listed in §10.1
are applied voluntarily in the User's interest.

---

## 11. Rights of the data subject

**11.1.** The User holds the following rights with respect to Local data:

| # | Right | GDPR article | 152-FZ article | How to exercise |
|---|---|---|---|---|
| 1 | Access | 15 | 14 | open the application folder |
| 2 | Rectification | 16 | 20 | edit files manually |
| 3 | Erasure | 17 | 21 | settings → cleanup, or manually |
| 4 | Restriction of processing | 18 | 16 | delete the corresponding files |
| 5 | Data portability | 20 | 20 | copy the Local data files |
| 6 | Object | 21 | 16 | stop using the Application |
| 7 | Withdraw consent | 7(3) | 9 | uninstall the Application |
| 8 | Lodge a complaint | 77 | 23–24 | contact the supervisory authority of your jurisdiction |

**11.2.** Because the Developer does not receive Local data, rights 1–7 are
exercised by the User directly on the Device.

**11.3.** Under CCPA/CPRA (California), VCDPA (Virginia), CPA (Colorado), and
CTDPA (Connecticut) the User has analogous rights: to know, delete, correct,
and opt out of sale or sharing. Because the Developer does not sell or share
data and does not receive it, these rights are exercised locally, and no
request to the Developer is required.

**11.4.** The right under §11.1.8 is exercised in the manner prescribed by
the law of the User's jurisdiction (in Russia — Art. 23 152-FZ).

---

## 12. Children

**12.1.** The Application is not intended for use by persons below the age
at which, under their jurisdiction's law, they can independently consent to
the processing of personal data (Art. 8 GDPR; COPPA in the US — under 13;
Art. 9 152-FZ — under 18 unless otherwise provided).

**12.2.** The Developer does not knowingly collect or process data of persons
below that age.

**12.3.** If the User is a parent or guardian and believes that a minor is
using the Application without proper consent, they may uninstall the
Application from the Device.

---

## 13. Changes to this Policy

**13.1.** The Developer may amend this Policy.

**13.2.** The current version is published in the project repository at the
address specified in §0.

**13.3.** Changes affecting categories of processed data, network
interactions, or User rights are recorded in the Changelog.

**13.4.** Continued use of the Application after changes are published
constitutes acceptance of the new version.

---

## 14. Contact

**14.1.** Questions concerning this Policy: repository Issues system:
`https://github.com/AkashaForge/ama-gi-player/issues`

**14.2.** The Developer does not hold the User's personal data, so requests
for access, rectification, erasure, or portability need not be addressed to
the Developer (see §11.2).

---

## Annex A — Technical data inventory

### A.1. Watch history

| Field | Value |
|---|---|
| File | `data/app_data.db` |
| Format | SQLite 3 (WAL) |
| Table | `user_history` |
| Fields | `kp_id INTEGER`, `movie_title TEXT`, `current_seconds REAL`, `duration_sec REAL`, `updated_at TIMESTAMP` |
| Outbound transfer | none |

### A.2. Poster cache

| Field | Value |
|---|---|
| Folder | `data/cache/` |
| Format | JPEG, PNG |
| Naming | `{kp_id}.jpg` |
| Outbound transfer | none |

### A.3. Metadata cache

| Field | Value |
|---|---|
| Folders | `data/cache/short/`, `data/cache/full/`, `data/cache/lists/` |
| Format | JSON (one file per entry) |
| Naming | `{id}.json` (short/full), `{hash}.json` (lists) |
| Populated | only when Kinopoisk API is used (`private` mode) |
| Outbound transfer | none |

### A.4. Film catalog

| Field | Value |
|---|---|
| File | `data/whitelist.db` (working), `data/whitelist_seed.db` (bundled) |
| Format | SQLite 3 |
| Table | `movie_whitelist` |
| Contains user data | no (public-domain film metadata from Internet Archive) |
| Outbound transfer | none |

### A.5. Mode selection

| Field | Value |
|---|---|
| File | `data/mode.txt` |
| Format | plain text (`public` or `private`) |
| Contains user data | no (preference only) |
| Outbound transfer | none |

### A.6. Source list

| Field | Value |
|---|---|
| File | `data/sources.txt` |
| Format | plain text, one record per line |
| Record schema | `<type>\|<base_url>\|<display_name>` |
| Outbound transfer | only as HTTP requests to the listed sources |

### A.7. API keys

| Field | Value |
|---|---|
| File | `.env` (next to executable) |
| Format | plain text, `KEY=value` |
| Fields | `KP_API_KEY`, `ARIA2_SECRET` |
| Personal data | `KP_API_KEY` identifies the User to Kinopoisk API |
| Outbound transfer | `KP_API_KEY` → `kinopoiskapiunofficial.tech` only, only in `private` mode |
| Retention | until deleted by User |

### A.8. Configuration defaults

| Field | Value |
|---|---|
| File | `config.py` |
| Format | Python source code (read-only module) |
| Contains user data | **no** |
| Outbound transfer | none |

### A.9. Diagnostics

| Field | Value |
|---|---|
| Output | console (stderr) |
| Persisted to disk | **no** by default |
| Contains personal data | no (see Annex C) |

---

## Annex B — Network endpoints

### B.1. Internet Archive

| Field | Value |
|---|---|
| Host | `archive.org`, `*.archive.org` |
| Protocol | HTTPS |
| Endpoints | `/advancedsearch.php`, `/metadata/<id>`, `/download/<id>/<file>`, `/services/img/<id>` |
| Headers | `User-Agent: Amagi-Player/<version>`, `Accept`, `Accept-Language` |
| Triggered by | search, opening a card, playback |

### B.2. Kinopoisk API

| Field | Value |
|---|---|
| Host | `kinopoiskapiunofficial.tech` |
| Protocol | HTTPS |
| Endpoints | `/api/v2.1/films/search-by-keyword`, `/api/v2.2/films/<id>` |
| Headers | `X-API-KEY: <KP_API_KEY>`, `User-Agent: Amagi-Player/<version>`, `Accept` |
| Triggered by | **only** in `private` mode when `KP_API_KEY` is set |

### B.3. User-defined sources

| Field | Value |
|---|---|
| Host | determined by `data/sources.txt` |
| Protocol | HTTPS (recommended), HTTP |
| Endpoints | determined by the source type |
| Headers | `User-Agent: Amagi-Player/<version>`, `Accept` |
| Triggered by | search over user sources |

### B.4. Local external indexer

| Field | Value |
|---|---|
| Host | `127.0.0.1`, `localhost` |
| Protocol | HTTP |
| Endpoints | determined by the indexer configuration |
| Headers | standard HTTP |
| Triggered by | when the User connects an indexer |

### B.5. BitTorrent swarms of Internet Archive

| Field | Value |
|---|---|
| Protocol | BitTorrent (libtorrent) |
| Trackers | public trackers from the Internet Archive `.torrent` file |
| Data transmitted | IP address, port, BitTorrent peer-id |
| Triggered by | playback in `private` mode only |

---

## Annex C — Logging specification

**C.1.** The Application writes diagnostics to **console (stderr)** only.
No persistent log files are created by default.

**C.2.** The following are **not** written to diagnostics:

- IP addresses of Sources;
- the User's search queries;
- HTTP header contents;
- the User's personal data (including API keys).

**C.3.** The following **are** written to diagnostics:

- timestamps;
- logging levels;
- module identifiers;
- error messages and stack traces.

**C.4.** Diagnostics are not transmitted to the Developer and are not sent
to any network endpoint.

**C.5.** If file logging is enabled by the User, the location and retention
are determined by the User's configuration; the Developer does not receive
these logs.

---

## Annex D — Compliance matrix

| Norm | Applicability | Status |
|---|---|---|
| **European Union** | | |
| GDPR Art. 5 (principles) | applicable (reference) | complied (§4) |
| GDPR Art. 6 (lawful basis) | applicable (reference) | consent + agreement (§4.1) |
| GDPR Art. 12(7) (layered notice) | applicable (reference) | structure implements it |
| GDPR Art. 13–14 (information) | applicable (reference) | §§5–9 |
| GDPR Art. 15–21 (rights) | applicable (reference) | §11 |
| GDPR Art. 30 (records) | not applicable | Developer is not a controller (§3.1) |
| GDPR Art. 32 (security) | not applicable | Developer does not process (§10.3) |
| GDPR Art. 44–49 (transfer) | not applicable | no transfer (§8.3) |
| **United States** | | |
| COPPA (15 U.S.C. §§ 6501–6506) | applicable | §12 |
| CCPA/CPRA (California) | applicable | rights exercised locally (§11.3) |
| VCDPA (Virginia) | applicable | analogous to CCPA (§11.3) |
| CPA (Colorado) | applicable | analogous to CCPA (§11.3) |
| CTDPA (Connecticut) | applicable | analogous to CCPA (§11.3) |
| **Russian Federation** | | |
| 152-FZ Art. 3 (definitions) | applicable (reference) | §1 |
| 152-FZ Art. 5 (principles) | applicable (reference) | §4.2 |
| 152-FZ Art. 9 (consent) | applicable (reference) | §4.1 |
| 152-FZ Art. 14 (access) | applicable (reference) | §11.1 |
| 152-FZ Art. 18 (informing) | applicable (reference) | §§5–9 |
| 152-FZ Art. 19 (security) | not applicable | Developer does not process (§10.3) |
| 152-FZ Art. 22 (notification to Roskomnadzor) | not applicable | Developer is not an operator (§3.1) |
| 152-FZ cross-border transfer (Art. 12) | not applicable | no transfer (§8.3) |
| **Other (reference only)** | | |
| LGPD (Brazil) | applicable (reference) | analogous to GDPR |
| PIPL (China) | not applicable | Developer is not a personal-information processor |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-01-01 | Initial publication. |
| 2.0 | 2026-10-28 | Corrected data inventory to match actual file paths (`data/app_data.db`, `data/cache/`, `.env`); removed fictitious `config.json` and `cache/metadata.db`; added `.env`, `data/mode.txt`, `data/whitelist.db`, `data/sources.txt`; clarified that `config.py` is a source-code module with no user data; added Kinopoisk API endpoint (B.2); added explicit API-key disclosure in §6.2; added US state laws and 152-FZ to compliance matrix; removed fictitious file-based log rotation (diagnostics are console-only by default). |

---

<div align="right">

*Amagi-Player · Privacy Policy v2.0 · 2026-10-28*

</div>
