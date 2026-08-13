"""
pii_faker.py

Generates fake replacement values for detected PII, guaranteeing that the
same real value always maps to the same fake value everywhere in the
document (e.g. "Rashi Patil" -> "John Doe" consistently, and any email
built from that name is kept consistent with it where possible).
"""

import re
import itertools

FIRST_NAMES = [
    "John", "Peter", "Emma", "Liam", "Olivia", "Noah", "Ava", "William",
    "Sophia", "James", "Isabella", "Benjamin", "Mia", "Lucas", "Charlotte",
    "Henry", "Amelia", "Alexander", "Harper", "Michael", "Evelyn", "Daniel",
    "Abigail", "Matthew", "Emily", "Jackson", "Elizabeth", "David", "Sofia",
    "Joseph",
]
LAST_NAMES = [
    "Doe", "Parker", "Smith", "Johnson", "Williams", "Brown", "Jones",
    "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez",
    "Lopez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson",
    "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez",
    "Clark", "Ramirez", "Lewis",
]
COMPANY_NAMES = [
    "Acme Industries Limited", "Northstar Corporation", "Bluewater Holdings",
    "Summit Enterprises Ltd.", "Vertex Global Limited", "Silverline Corp",
    "Horizon Manufacturing Ltd.", "Crestview Industries", "Meridian Group",
    "Falcon Enterprises Limited", "Ironwood Holdings", "Pinnacle Corp",
    "Cobalt Industries Ltd.", "Lakeside Manufacturing", "Redstone Group",
]
STREETS = ["Maple Avenue", "Oak Street", "Cedar Lane", "Elm Road",
           "Birchwood Drive", "Willow Court", "Aspen Way", "Magnolia Boulevard"]
CITIES = ["Springfield", "Fairview", "Riverside", "Georgetown", "Clinton",
          "Madison", "Franklin", "Greenville"]


class FakeValueGenerator:
    """Deterministic, collision-avoiding fake value generator with a
    persistent original -> fake mapping (kept per PII type so an email
    and a person name never collide on the same fake string)."""

    def __init__(self):
        self._map = {}  # (label, original_normalized) -> fake
        self._used = {}  # label -> set(fake values already assigned)
        self._name_cycle = itertools.cycle(
            (f, l) for f in FIRST_NAMES for l in LAST_NAMES
        )
        self._company_cycle = itertools.cycle(COMPANY_NAMES)
        self._addr_counter = itertools.count(1)
        self._phone_counter = itertools.count(1000000)
        self._card_counter = itertools.count(1)
        self._ip_counter = itertools.count(1)

    def _key(self, label, original):
        return (label, original.strip().lower())

    def get(self, label, original):
        key = self._key(label, original)
        if key in self._map:
            return self._map[key]

        if label == "PERSON":
            fake = self._fake_person()
        elif label == "COMPANY":
            fake = self._fake_company()
        elif label == "EMAIL":
            fake = self._fake_email(original)
        elif label == "PHONE":
            fake = self._fake_phone(original)
        elif label == "ADDRESS":
            fake = self._fake_address()
        elif label == "SSN":
            fake = self._fake_ssn()
        elif label == "CREDIT_CARD":
            fake = self._fake_card()
        elif label == "IP_ADDRESS":
            fake = self._fake_ip()
        elif label == "DOB":
            fake = self._fake_dob()
        else:
            fake = "[REDACTED]"

        self._map[key] = fake
        self._used.setdefault(label, set()).add(fake)
        return fake

    # -- individual fakers -------------------------------------------------

    def _fake_person(self):
        f, l = next(self._name_cycle)
        return f"{f} {l}"

    def _fake_company(self):
        return next(self._company_cycle)

    def _fake_email(self, original):
        # Try to build "john.doe@example.com" style consistent with a
        # person fake if the local part looks like a name; otherwise
        # generate a generic fake email.
        local, _, domain = original.partition("@")
        # Reuse a person mapping if this local part matches one already faked
        for (lbl, orig_norm), fake in self._map.items():
            if lbl == "PERSON":
                orig_local_guess = orig_norm.replace(" ", ".")
                if orig_local_guess in local.lower().replace("_", "."):
                    fname, lname = fake.split(" ", 1)
                    return f"{fname.lower()}.{lname.lower()}@example.com"
        f, l = next(self._name_cycle)
        return f"{f.lower()}.{l.lower()}@example.com"

    def _fake_phone(self, original):
        n = next(self._phone_counter)
        digits = str(n).rjust(7, "0")[-7:]
        if original.strip().startswith("+91") or original.strip().startswith("91"):
            return f"+91 {digits[:5]} {digits[5:]}"
        return f"+1 555-{digits[:3]}-{digits[3:7] if len(digits) >= 7 else digits}"

    def _fake_address(self):
        import random
        n = next(self._addr_counter)
        street = STREETS[n % len(STREETS)]
        city = CITIES[n % len(CITIES)]
        return f"{100 + n} {street}, {city}, ST {10000 + n}"

    def _fake_ssn(self):
        n = next(self._card_counter)
        return f"{100 + n:03d}-{10 + n % 89:02d}-{1000 + n:04d}"

    def _fake_card(self):
        n = next(self._card_counter)
        return f"4111 1111 1111 {1000 + n % 9000:04d}"

    def _fake_ip(self):
        n = next(self._ip_counter)
        return f"10.0.{(n // 254) % 254}.{n % 254 + 1}"

    def _fake_dob(self):
        n = next(self._addr_counter)
        day = (n % 28) + 1
        month = (n % 12) + 1
        year = 1970 + (n % 30)
        return f"{day:02d}/{month:02d}/{year}"
