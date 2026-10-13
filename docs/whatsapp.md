# WhatsApp integration

Configure Meta WhatsApp Business Cloud API to call `/api/v1/whatsapp/webhook` (GET verification and POST messages). The intake accepts a free-text emergency description, then a NIPOST digital postcode or a WhatsApp location message. A postcode is resolved with the configured postcode provider; a demo location or actual returned coordinates are required for distance ranking. `HELP` remains an optional way to start the conversation.

`WHATSAPP_PROVIDER=mock` permits local webhook flows without Meta credentials. Replies are stored as mocked messages and are not sent to a phone. Live Meta mode requires a public HTTPS callback, Meta access token, phone number ID, API version, app secret, verify token, and subscribed message webhook events. Secrets stay in backend environment configuration.

No message or dispatch is sent to a real response team by this prototype. An operator reviews the incident, confirms its location and urgency, chooses the suggested available unit, and records a simulated dispatch for demo units. A real dispatch needs explicit integration with the relevant response agencies and their operational systems.
