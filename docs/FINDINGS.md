# Findings from exploring eSuite (2026-09-30 / 10-01)

Observed while building the suite. Each one changed how a test asserts, so the reasoning is recorded here.

## BUG-01 - Deleted company stays in the Companies list as "Active" until the next login

- **Steps:** Companies -> Manage -> Delete -> tick "I understand & agree to delete" -> Confirm.
- **Expected:** the company disappears from the Companies list.
- **Actual:** you are redirected to Companies and the header count drops by one (e.g. 570 -> 569), but the card is
  still listed as *Active*, and it stays for at least 5 minutes in the same session. It disappears only after a fresh login.
- **Evidence:** `GET api-hermes.edot.id/api/v1/company/<id>` returns `404 company not found` and
  `GET /api/v1/company` (behind the header count) no longer contains it. `GET /api/v1/companies`, which
  renders the cards, still returns it with `"active": true`. The card list follows the login token's
  workspace list, which is not refreshed on delete.
- **Impact on the suite:** the delete check asserts the two authoritative signals (404 on the record,
  absent from the account's company API) and deliberately does not assert the card list.
- **Side effect:** some of the ~570 cards on the shared account may be companies that are already deleted.

## BUG-02 - Company Name silently refuses input over 30 characters

- **Steps:** Register Company step 1 -> type or paste a name longer than 30 characters.
- **Expected:** a `maxlength` that truncates, or a validation message.
- **Actual:** the change is rejected outright. An empty field stays empty; a filled field keeps its previous value.
  There is no message and no `maxlength` attribute, and Next stays disabled with no hint why.
- **Impact on the suite:** generated names are capped at 21 characters so the 9-character run tag fits.
  Test WEB-COMP-05 pins the boundary (30 accepted, 32 refused).

## BUG-03 - Deleted company lookup answers HTTP 500 (sometimes 404)

- **Steps:** delete a company, then open its Manage URL (the page calls `GET /api/v1/company/<id>`).
- **Expected:** a consistent `404 Not Found`.
- **Actual:** `{"status":404,"message":"company not found"}` right after one delete, and
  `{"status":500,"message":"company not found"}` for others (5120785, 5120791). A "not found" should not be a server error.
- **Impact on the suite:** the delete check asserts `status >= 400` + the message + absence from the account's company list,
  and attaches the status it saw.

## Behaviour notes (not bugs, but they shape the automation)

- **New company not immediately accessible:** right after registration the Manage page can render empty
  (the company API has not been granted to the session yet). `wait_until_accessible` reloads, with a limit,
  until the API serves the company.
- **Dropdown text is truncated** to 20 characters + "..." (e.g. "Transportation and L..."), and the full value
  is not in the DOM. The detail test checks the display value in the UI and the full values via the company API.
- **Branch step (3/3):** Branch Name is sometimes pre-filled asynchronously and sometimes not. The page object
  types it itself so the step is deterministic.
- **Postal Code** is derived from the Sub District and is read-only.
- **Phone** is typed after a fixed `+62` prefix and stored as `+62<number>`.
- **The account is shared by every candidate**, so counts can change under us. Assertions use our own IDs,
  never the total number of companies.
- **eWork blocks mock locations** ("Your location is invalid - Please turn off your fake GPS"). Maestro's `setLocation`
  triggers it, so flows never set a location. The customer address is typed and chosen from the cascade instead.
- **eWork login input can be lost on cold start:** once, Company ID stayed empty (the keyboard was still animating).
  The login sub-flow now waits for animations and asserts each field's value.
- **A new company's user cannot use eWork:** a user created in eSuite for a brand-new company is refused with
  "Failed to login. Please contact Sales Admin." (SFA-side salesman setup is missing). MOB-LOGIN-02 asserts this.
- **No `data-testid` anywhere** in eSuite or the Account Center. Locators use role + name, then placeholder or `name`,
  then label-anchored CSS, and text only where the element has nothing else.
