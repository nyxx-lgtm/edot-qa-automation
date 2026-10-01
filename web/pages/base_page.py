import allure
from playwright.sync_api import APIResponse, Locator, Page, Response, expect

# Login bounces through the eDOT Account Center (cronus.edot.id) and back, and
# the shared environment can be slow, so navigation-level waits get more room.
REDIRECT_TIMEOUT_MS = 30_000
# Dropdowns show at most 20 characters of the selected value, then "...".
COMBOBOX_DISPLAY_MAX = 20


def as_displayed(value: str) -> str:
    """How a dropdown renders a selected value, e.g. 'Transportation and L...'."""
    return value if len(value) <= COMBOBOX_DISPLAY_MAX else value[:COMBOBOX_DISPLAY_MAX] + "..."


class BasePage:
    def __init__(self, page: Page):
        self.page = page
        # Radix dropdowns render their options in a portal: either a menu or a popover
        # dialog. Closed menus stay in the DOM, so only the open one is targeted.
        self._open_popup = page.locator("[role=menu][data-state=open], [role=dialog][data-state=open]")

    def refetch(self, response: Response) -> APIResponse:
        """Re-issue an API call the page just made, with the same auth header.

        Reading the body of an intercepted response is unreliable here: when the app repeats the
        call or navigates away, Chrome discards the body ("No resource with given identifier").
        A direct request always has a readable body.
        """
        auth = response.request.all_headers().get("authorization")
        return self.page.request.get(response.url, headers={"authorization": auth} if auth else None)

    def field_combobox(self, label: str) -> Locator:
        """Dropdown found through its visible label.

        eSuite's comboboxes have no accessible name, test id or stable id (the ids are
        generated), and the label is a <span> not linked to the control. The label text is
        the most stable anchor. The regex is anchored at the start so 'District' does not
        also match 'Sub District'.
        """
        return self.page.locator(f"div:has(> span:text-matches('^{label}')) [role=combobox]")

    def choose(self, label: str, option: str, search: bool = False):
        with allure.step(f"Choose {label}: {option}"):
            self.field_combobox(label).click()
            if search:
                # Long lists (province, city, ...) are searched server-side.
                self._open_popup.get_by_placeholder("Search").fill(option)
            self._open_popup.get_by_role("option", name=option, exact=True).first.click()
            expect(self.field_combobox(label)).to_have_text(as_displayed(option))
