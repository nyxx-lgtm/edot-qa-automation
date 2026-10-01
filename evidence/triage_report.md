# Failure triage report

> Every verdict below is a **proposal for a human reviewer**. Nothing was filed, closed, re-written or skipped; failed tests remain failed.

| Test | Verdict | Stopped at |
|---|---|---|
| WEB-COMP-02 Company detail matches the registration input field by field | **script/environment defect** | 2 - locator hit the wrong element |

## WEB-COMP-02 Company detail matches the registration input field by field

- **Verdict (proposal):** script/environment defect
- **Stopped at evidence step:** 2 - locator hit the wrong element
- **Test:** `web/tests/test_company.py::TestCompany::test_company_detail_matches_input`
- **Allure status:** failed

**Evidence**

- It is an assertion failure (`AssertionError`), not an exception.
- The locator resolved to a single element.
- Every earlier step and every fixture passed.
- AI (proposal): The failing assertion is on the email field (expected 'sales.qabeb4eb@miratek.example.com'), but the call log shows it resolved 'get_by_placeholder("Input Company Name")', an input with value 'PT Mitra Teknik QABEB4EB'. That is the company name field, not the email field.

_AI: claude-sonnet-5-5, 3184 in / 219 out tokens_

<details><summary>Failure message</summary>

```
AssertionError: Locator expected to have Value 'sales.qabeb4eb@miratek.example.com'
Actual value: PT Mitra Teknik QABEB4EB 
Call log:
  - LocatorAssertions.to_have_value with timeout 5000ms
  - waiting for get_by_placeholder("Input Company Name")
    9 × locator resolved to <input type="text" placeholder="Input Company Name" value="PT Mitra Teknik QABEB4EB" class="flex h-full w-full min-w-14 grow bg-transparent px-3 py-2 text-sm outline-none file:mr-2 file:border-0 file:bg-transparent file:px-0 file:text-sm file:font-medium placeholder:text-gray-300 read-only:bg-neutral-grey-200-bg disabled:cursor-not-allowed disabled:opacity-50"/>
      - unexpected value "PT Mitra Teknik QABEB4EB"
```
</details>
