"""
Konfigurasjon for kommer-for-salg-norge — de syv største byene i Norge.

Sporer "Kommer for salg"-prosjekter (URL-format /realestate/planned/).
"""

MUNICIPALITIES = [
    {"name": "Oslo",         "finn_location": "0.20061"},
    {"name": "Bergen",       "finn_location": "1.22046.20220"},
    {"name": "Stavanger",    "finn_location": "1.20012.20196"},
    {"name": "Trondheim",    "finn_location": "1.20016.20318"},
    {"name": "Tromsø",       "finn_location": "1.20019.20413"},
    {"name": "Drammen",      "finn_location": "1.22030.20110"},
    {"name": "Kristiansand", "finn_location": "1.22042.20179"},
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

DELAY_BETWEEN_REQUESTS_S = 4
REQUEST_TIMEOUT_S = 25
