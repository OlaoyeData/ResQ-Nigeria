from app.core.config import settings


class WhatsAppProvider:
    async def send_text(self, to: str, text: str) -> None:
        raise NotImplementedError


class MockWhatsAppProvider(WhatsAppProvider):
    async def send_text(self, to: str, text: str) -> None:
        return None


class MetaWhatsAppProvider(WhatsAppProvider):
    async def send_text(self, to: str, text: str) -> None:
        import httpx
        if not settings.whatsapp_api_version:
            raise RuntimeError("Set WHATSAPP_API_VERSION to a version supported by your Meta app.")
        url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
        payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()


def get_whatsapp_provider():
    return MetaWhatsAppProvider() if settings.whatsapp_provider.lower() == "meta" else MockWhatsAppProvider()
