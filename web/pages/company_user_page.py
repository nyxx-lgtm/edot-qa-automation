import allure
from playwright.sync_api import expect

from web.pages.base_page import BasePage

# Creating the user also provisions it in the Account Center; it takes well over 5 seconds.
USER_CREATE_TIMEOUT_MS = 30_000


class CompanyUserPage(BasePage):
    """Companies -> Manage -> Company User -> + Add User (two tabs: General Info, Branch)."""

    def __init__(self, page):
        super().__init__(page)
        self.add_user_button = page.get_by_role("button", name="+ Add User")
        # Pagination footer, rendered once the user table has loaded ("Showing 1 of 0, from 0 entries.").
        self.table_loaded = page.get_by_text("entries.", exact=False)
        self.dialog = page.get_by_role("dialog").first
        # Inputs inside the dialog: placeholders are the only stable attributes (ids are generated).
        self.name = self.dialog.get_by_placeholder("Input Name")
        self.username = self.dialog.get_by_placeholder("Input Username")
        self.email = self.dialog.get_by_placeholder("Input Email")
        self.phone = self.dialog.get_by_placeholder("Input Phone")
        self.password = self.dialog.get_by_placeholder("Input Password")
        self.next_button = self.dialog.get_by_role("button", name="Next")
        self.add_branch_button = self.dialog.get_by_role("button", name="Add Branch")
        self.submit_button = self.dialog.get_by_role("button", name="Submit Data")
        # The branch picker opens as a second dialog on top of the first.
        self.branch_picker = page.get_by_role("dialog").filter(has_text="Add Branch").last

    def open(self, manage_url: str):
        self.page.goto(manage_url.replace("/profile", "/company-user"))
        # "+ Add User" is rendered (faded) before the page is ready and ignores clicks until then.
        expect(self.table_loaded).to_be_visible()
        return self

    def row(self, username: str):
        return self.page.get_by_role("row").filter(has_text=username)

    def add_user(self, name: str, username: str, email: str, phone: str, password: str, branch: str):
        with allure.step(f"Add company user '{username}'"):
            self.add_user_button.click()
            expect(self.name).to_be_visible()
            self.name.fill(name)
            self.username.fill(username)
            self.email.fill(email)
            self.phone.fill(phone)
            self.password.fill(password)
            self.next_button.click()

            self.add_branch_button.click()
            # Narrow the picker to our branch via its search box, so exactly one row (and one
            # checkbox) is left, then confirm each state change before moving on.
            self.branch_picker.get_by_placeholder("Search").fill(branch)
            expect(self.branch_picker.get_by_text(branch, exact=True)).to_be_visible()
            checkbox = self.branch_picker.get_by_role("checkbox")
            expect(checkbox).to_have_count(1)
            checkbox.click()
            expect(checkbox).to_have_attribute("aria-checked", "true")
            self.branch_picker.get_by_role("button", name="Add", exact=True).click()

            expect(self.dialog.get_by_text(branch, exact=True)).to_be_visible()
            expect(self.submit_button).to_be_enabled()
            self.submit_button.click()

            # Success modal (Indonesian UI): "User Berhasil Dibuat" = "User created successfully".
            success = self.page.get_by_role("dialog").filter(has_text="User Berhasil Dibuat")
            expect(success).to_be_visible(timeout=USER_CREATE_TIMEOUT_MS)
            success.get_by_role("button", name="Tutup").click()   # "Tutup" = "Close"
        with allure.step(f"Verify '{username}' is listed"):
            # The table does not always refresh after the modal closes; reload it, then check the row.
            self.page.reload()
            expect(self.table_loaded).to_be_visible()
            expect(self.row(username)).to_be_visible()
