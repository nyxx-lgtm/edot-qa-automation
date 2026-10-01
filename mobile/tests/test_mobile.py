import allure

from ai.data_generator import synthetic_ktp
from config import settings
from config.test_constants import (ADDRESS_CASCADE, ADDRESS_TYPE, CHANNEL_TYPE, CUSTOMER_TYPE,
                                   LOGIN_REFUSED_MESSAGE)
from mobile.maestro import log_created_customer, regex_escaped, run_flow


def assert_flow_passed(result):
    # The Maestro flow holds the assertions; a non-zero exit means one of them (or a step) failed.
    tail = "\n".join(result.output.splitlines()[-25:])
    assert result.returncode == 0, f"Maestro flow failed (exit {result.returncode}):\n{tail}"


@allure.feature("Mobile - Login")
class TestMobileLogin:

    @allure.title("MOB-LOGIN-01 Valid salesman login shows the dashboard")
    def test_login_shows_dashboard(self, maestro_ready, sfa_credentials):
        result = run_flow("login_dashboard.yaml", sfa_credentials, secrets=[sfa_credentials["EWORK_PASSWORD"]])
        assert_flow_passed(result)

    @allure.title("MOB-LOGIN-02 Handoff: the web-created company's user is refused with 'Please contact Sales Admin'")
    def test_new_company_user_is_refused(self, maestro_ready, handoff_user):
        env = {"HANDOFF_COMPANY_ID": handoff_user.company_id, "HANDOFF_USERNAME": handoff_user.username,
               "HANDOFF_PASSWORD": handoff_user.password,
               **regex_escaped({"LOGIN_REFUSED_MESSAGE": LOGIN_REFUSED_MESSAGE})}
        result = run_flow("login_refused.yaml", env, secrets=[handoff_user.password])
        assert_flow_passed(result)


@allure.feature("Mobile - Customer")
class TestMobileCustomer:

    @allure.title("MOB-CUST-02 New customer is listed with the data entered (incl. MOB-CUST-01 KTP gate)")
    def test_create_customer(self, maestro_ready, sfa_credentials, generated_data):
        customer = generated_data.customer
        values = {"CUSTOMER_NAME": customer.name, "CUSTOMER_PHONE": customer.phone,
                  "CUSTOMER_EMAIL": customer.email, "CUSTOMER_CONTACT": customer.contact_person,
                  "CUSTOMER_ADDRESS": customer.street_address}
        selectors = {"CHANNEL_TYPE": CHANNEL_TYPE, "CUSTOMER_TYPE": CUSTOMER_TYPE, "ADDRESS_TYPE": ADDRESS_TYPE,
                     "PROVINCE": ADDRESS_CASCADE["province"], "CITY": ADDRESS_CASCADE["city"],
                     "DISTRICT": ADDRESS_CASCADE["district"], "SUB_DISTRICT": ADDRESS_CASCADE["sub_district"]}
        env = {**sfa_credentials, **values, **regex_escaped(values), **regex_escaped(selectors),
               "CUSTOMER_KTP": synthetic_ktp()}

        try:
            result = run_flow("create_customer.yaml", env, secrets=[sfa_credentials["EWORK_PASSWORD"]])
        finally:
            # Recorded whatever happens next: "after_confirm" is only taken once the app saved it.
            if any((settings.MOBILE_OUTPUT_DIR / f"create_customer-{settings.RUN_ID}").rglob("after_confirm.png")):
                log_created_customer({"name": customer.name, "run_id": settings.RUN_ID,
                                      "company_id": sfa_credentials["EWORK_COMPANY_ID"]})
        assert_flow_passed(result)
