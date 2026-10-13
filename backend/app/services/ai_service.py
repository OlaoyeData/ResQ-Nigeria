import re


class AIProvider:
    def classify_incident(self, description: str) -> dict:
        raise NotImplementedError


class MockAIProvider(AIProvider):
    """Assistive classifier. It never makes dispatch decisions."""
    def classify_incident(self, description: str) -> dict:
        text = description.lower()
        terms = {
            "medical": ["collapsed", "unconscious", "injured", "bleeding", "sick", "medical", "not responding", "can't breathe", "cannot breathe", "difficulty breathing", "chest pain", "seizure", "labour", "labor", "poison"],
            "fire": ["fire", "burning", "smoke", "flames", "building is on fire"],
            "road_accident": ["accident", "crash", "collision", "vehicle", "road", "hit by a car", "overturned"],
            "security": ["attack", "robbery", "gun", "threat", "security", "violence", "intruder", "kidnap", "kidnapping", "armed"],
        }
        scores = {kind: sum(1 for word in words if word in text) for kind, words in terms.items()}
        best = max(scores, key=scores.get)
        confidence = min(0.93, 0.58 + 0.12 * scores[best]) if scores[best] else 0.35
        if not scores[best]:
            best = "other"
        urgent_phrases = ["unconscious", "not responding", "trapped", "fire", "bleeding", "collapsed", "can't breathe", "cannot breathe", "difficulty breathing", "chest pain", "seizure", "heavy bleeding", "gun", "armed", "building is on fire"]
        urgency = "high" if any(w in text for w in urgent_phrases) else "medium"
        location = re.search(r"(?:at|near|on|beside|close to)\s+([^,.]+(?:,[^,.]+)?)", description, re.I)
        missing = []
        if not location:
            missing.append("exact_location")
        if len(description.strip()) < 12:
            missing.append("incident_details")
        return {"incident_type": best, "confidence": confidence, "urgency": urgency,
                "confidence_reason": "Free-text keyword triage for this portfolio demo; an operator must review it.",
                "urgency_reason": "A high-risk phrase was detected; verify the situation immediately." if urgency == "high" else "No high-risk phrase was detected; confirm urgency with the reporter.",
                "location_entities": [location.group(1).strip()] if location else [],
                "missing_information": missing,
                "summary": description.strip()[:240] or "No incident details provided."}

    def extract_location(self, description: str) -> list[str]:
        result = self.classify_incident(description)
        return result["location_entities"]

    def summarize_incident(self, description: str) -> str:
        return self.classify_incident(description)["summary"]

    def identify_missing_information(self, description: str, has_location: bool) -> list[str]:
        missing = self.classify_incident(description)["missing_information"]
        if has_location and "exact_location" in missing:
            missing.remove("exact_location")
        return missing

    def generate_follow_up_question(self, missing: list[str]) -> str:
        return "Please share your current location so we can verify where help is needed." if "exact_location" in missing else "Please describe what happened."


class AIService:
    def __init__(self, provider: AIProvider | None = None): self.provider = provider or MockAIProvider()
    def classify_incident(self, description: str) -> dict: return self.provider.classify_incident(description)
    def extract_location(self, description: str) -> list[str]: return self.provider.extract_location(description)
    def summarize_incident(self, description: str) -> str: return self.provider.summarize_incident(description)
    def identify_missing_information(self, description: str, has_location: bool) -> list[str]: return self.provider.identify_missing_information(description, has_location)
    def generate_follow_up_question(self, missing: list[str]) -> str: return self.provider.generate_follow_up_question(missing)
    def confidence_band(self, confidence: float) -> str:
        from app.core.config import settings
        if confidence >= settings.confidence_high: return "HIGH"
        if confidence >= settings.confidence_medium: return "MEDIUM"
        return "LOW"


ai_service = AIService()
