from datastructures.output.agency import AgencyID


class RouteName:
    ...


class RouteType:
    ...


class Route:
    id: int
    agency_id: AgencyID
    name: RouteName
    type: RouteType
    ...


class Routes:
    routes: list[Route]
    ...
