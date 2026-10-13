# NIPOST digital postcode integration

NIPOST describes the National Digital Postcode as an 11-character alphanumeric code associated with an addressable building. Its public site directs organisations to register for developer access and an API key. The exact current API endpoint, authentication details, and coordinate response schema must be confirmed using the access granted to this project; older postcode API notes in this repository are not proof that the new service is connected.

The adapter accepts a five-part display form such as `FC 02 A09 DB 09`, normalizes it to `FC-02-A09-DB-09`, and expects a lookup response to provide validity and coordinates. It does not claim an incident is geolocated for nearest-team matching unless latitude and longitude are present. Configure the official endpoint and credential in the backend only after NIPOST provides the current integration guide.

`NIPOST_PROVIDER=mock` supports the portfolio demo. `FC 02 A09 DB 09` resolves to a synthetic coordinate fixture in Abuja so the app can demonstrate nearest-team ranking. This fixture is not an official assignment of a postcode to a building and must never be presented as a real NIPOST lookup. Other syntactically valid codes stay pending and do not produce a nearest-team result.

Nearest-team distance is haversine straight-line distance, not road distance or travel-time estimation. Only available database-listed units with coordinates can be distance ranked. Unit capability and availability are demo/operator-entered values.

Official public information: [NIPOST Digital Postcode](https://postcode.gov.ng/) and [NIPOST's integration announcement](https://nipost.gov.ng/calling-innovation-hubs/).
