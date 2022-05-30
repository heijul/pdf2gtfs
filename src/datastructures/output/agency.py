class AgencyID:
    id: int = 0

    def __init__(self):
        self.id = AgencyID.id
        AgencyID.id += 1


class AgencyName:
    ...


class AgencyTimeZone:
    ...


class AgencyURL:
    ...


class Agency:
    id: AgencyID
    name: AgencyName
    url: AgencyURL
    timezone: AgencyTimeZone

    def __init__(self):
        self.id = AgencyID()
