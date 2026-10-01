"""Values that must match options that exist in eSuite dropdowns.

The AI may only *choose* from these lists; it never invents dropdown values,
otherwise the web test would fail on data rather than on behaviour.
Captured from the live Register Company form on 2026-09-30.
"""

INDUSTRY_OPTIONS = [
    "Retail",
    "Real Estate",
    "Nonprofit and Social Services",
    "Manufacturing",
    "Hospitality",
    "Food & Beverage",
    "Finance and Banking",
    "Transportation and Logistics",
    "Telecommunications",
    "Technology",
    "Construction",
    "Mining and Metals",
    "Automotive",
    "Fast Moving Customer Goods (FMCG)",
    "Entertainment and Media",
    "Energy",
    "Agriculture",
    "Healthcare",
    "Education",
]

COMPANY_TYPE = "Distributor"
LANGUAGE = "English"  # options: Indonesia, English

# Dependent cascade Country -> Province -> City -> District -> Sub District ("Zone" in
# the brief) -> Postal Code. Postal Code is derived by eSuite from the Sub District and is
# read-only, so it is an expected value, not an input.
# Fixed on purpose: it exercises the cascade without random combinations that may not exist.
ADDRESS_CASCADE = {
    "country": "Indonesia",
    "province": "DKI JAKARTA",
    "city": "JAKARTA SELATAN",
    "district": "KEBAYORAN BARU",
    "sub_district": "SENAYAN",
    "postal_code": "12190",
}

BRANCH_NAME = "Headquarter"


# eWork SFA - New Customer Registration (options captured from the app on 2026-10-01).
EWORK_APP_ID = "id.edot.ework"
CHANNEL_TYPE = "General Trade (GT)"
CUSTOMER_TYPE = "Retailer Small"
ADDRESS_TYPE = "Delivery Address"
# No device location is set on purpose: eWork detects mock GPS (Maestro setLocation) and blocks
# the app with "Your location is invalid". The address is typed and chosen from the cascade instead.
LOGIN_REFUSED_MESSAGE = "Failed to login. Please contact Sales Admin."
