"""Generate weekly marketing insights with OpenAI."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from app.analyzer import load_and_analyze_data
except ImportError:
    try:
        from analyzer import load_and_analyze_data
    except ImportError:
        try:
            from app.analyzer import analyze_campaigns as load_and_analyze_data
        except ImportError:
            from analyzer import analyze_campaigns as load_and_analyze_data


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "campaigns.csv"
EXPECTED_TYPES = ["victoire", "alerte", "recommandation"]

SYSTEM_PROMPT = """
Tu es un analyste marketing senior francophone, tres rigoureux et tres concret.
Tu analyses des performances hebdomadaires de campagnes marketing.

Contraintes obligatoires :
- Reponds uniquement avec du JSON valide.
- Ne renvoie aucun texte avant ou apres le JSON.
- Le JSON doit contenir exactement une cle "insights".
- "insights" doit contenir exactement 3 objets, dans cet ordre :
  1. victoire
  2. alerte
  3. recommandation
- Chaque objet doit contenir exactement :
  - "type"
  - "title"
  - "message"
- "victoire" = meilleure opportunite a amplifier
- "alerte" = probleme le plus urgent a corriger
- "recommandation" = action concrete a executer la semaine prochaine
- Le contenu doit etre specifique aux donnees fournies.
- Le ton doit etre clair, business et actionnable.
""".strip()

INSIGHTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "insights": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": EXPECTED_TYPES,
                    },
                    "title": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["type", "title", "message"],
            },
        }
    },
    "required": ["insights"],
}


def build_prompt(data: dict[str, Any]) -> str:
    """Build the user prompt sent to the model."""
    summary = data.get("summary", {})
    campaigns = data.get("campaigns", [])

    payload = {
        "business_context": {
            "minimum_acceptable_roas": 2.5,
            "target_ctr": 3.5,
            "weekly_total_budget": summary.get("total_spend"),
        },
        "summary": summary,
        "campaigns": campaigns,
        "required_output": {
            "insights": [
                {"type": "victoire", "title": "string", "message": "string"},
                {"type": "alerte", "title": "string", "message": "string"},
                {"type": "recommandation", "title": "string", "message": "string"},
            ]
        },
    }

    return (
        "Analyse les performances hebdomadaires suivantes et produis exactement 3 insights JSON.\n"
        "La victoire doit identifier la meilleure opportunite a amplifier.\n"
        "L alerte doit identifier le probleme le plus urgent a traiter.\n"
        "La recommandation doit proposer une action concrete pour la semaine prochaine.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _validate_insights(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the JSON shape returned by the model."""
    insights = payload.get("insights")
    if not isinstance(insights, list) or len(insights) != 3:
        raise ValueError("Model response must contain exactly 3 insights.")

    actual_types = [item.get("type") for item in insights if isinstance(item, dict)]
    if actual_types != EXPECTED_TYPES:
        raise ValueError("Model response must contain insight types in the expected order.")

    for item in insights:
        if not isinstance(item, dict):
            raise ValueError("Each insight must be an object.")
        if set(item.keys()) != {"type", "title", "message"}:
            raise ValueError("Each insight must contain only type, title, and message.")
        for field in ("type", "title", "message"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError("Each insight field must be a non-empty string.")

    return payload


def _campaign_name(campaign: dict[str, Any]) -> str:
    """Return a display name for a campaign."""
    return str(campaign.get("campaign") or campaign.get("name") or "Campagne inconnue")


def _campaign_ctr(campaign: dict[str, Any]) -> float:
    """Return campaign CTR as a float."""
    return float(campaign.get("ctr") or 0.0)


def _campaign_roas(campaign: dict[str, Any]) -> float:
    """Return campaign ROAS as a float."""
    return float(campaign.get("roas") or 0.0)


def _campaign_spend(campaign: dict[str, Any]) -> float:
    """Return campaign spend as a float."""
    return float(campaign.get("spend") or 0.0)


def _build_mock_insights(data: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic mock insights from campaign data."""
    campaigns = list(data.get("campaigns", []))
    summary = data.get("summary", {})

    if not campaigns:
        return {
            "insights": [
                {
                    "type": "victoire",
                    "title": "Aucune campagne a amplifier",
                    "message": "Aucune campagne n est disponible dans les donnees hebdomadaires.",
                },
                {
                    "type": "alerte",
                    "title": "Donnees manquantes",
                    "message": "Le fichier analyse ne contient aucune campagne exploitable.",
                },
                {
                    "type": "recommandation",
                    "title": "Verifier le chargement des donnees",
                    "message": "Controlez le CSV source avant de lancer la prochaine analyse hebdomadaire.",
                },
            ]
        }

    best_campaign = max(campaigns, key=lambda item: (_campaign_roas(item), _campaign_ctr(item)))
    urgent_campaign = min(campaigns, key=lambda item: (_campaign_roas(item), -_campaign_spend(item)))

    low_ctr_campaigns = [item for item in campaigns if _campaign_ctr(item) < 3.5]
    if low_ctr_campaigns:
        recommendation_campaign = max(low_ctr_campaigns, key=_campaign_spend)
        recommendation_message = (
            f"Retravaillez les creatives et le ciblage de {_campaign_name(recommendation_campaign)} "
            f"la semaine prochaine : CTR a {_campaign_ctr(recommendation_campaign):.2f}% "
            f"pour un spend de {_campaign_spend(recommendation_campaign):.0f}."
        )
    else:
        recommendation_campaign = best_campaign
        recommendation_message = (
            f"Augmentez progressivement le budget de {_campaign_name(recommendation_campaign)} "
            f"la semaine prochaine, car cette campagne combine un ROAS de "
            f"{_campaign_roas(recommendation_campaign):.2f}x et un CTR de "
            f"{_campaign_ctr(recommendation_campaign):.2f}%."
        )

    return {
        "insights": [
            {
                "type": "victoire",
                "title": f"Amplifier {_campaign_name(best_campaign)}",
                "message": (
                    f"{_campaign_name(best_campaign)} est la meilleure opportunite a amplifier cette semaine "
                    f"avec un ROAS de {_campaign_roas(best_campaign):.2f}x, au-dessus du seuil cible de 2.5x."
                ),
            },
            {
                "type": "alerte",
                "title": f"Corriger {_campaign_name(urgent_campaign)}",
                "message": (
                    f"{_campaign_name(urgent_campaign)} est le point le plus urgent a traiter avec un ROAS de "
                    f"{_campaign_roas(urgent_campaign):.2f}x, pour un budget engage de "
                    f"{_campaign_spend(urgent_campaign):.0f} sur la semaine."
                ),
            },
            {
                "type": "recommandation",
                "title": f"Action sur {_campaign_name(recommendation_campaign)}",
                "message": recommendation_message,
            },
        ]
    }


def _parse_model_json(raw_text: str) -> dict[str, Any]:
    """Parse model JSON safely."""
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON returned by model: {exc}") from exc

    return _validate_insights(parsed)


def generate_insights(data: dict[str, Any]) -> dict[str, Any]:
    """Generate three structured insights from analyzed campaign data."""
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    if not api_key:
        print(
            "Fallback mock mode enabled: OPENAI_API_KEY is missing. Returning deterministic local insights.",
            file=sys.stderr,
        )
        return _build_mock_insights(data)

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI Python SDK is not installed. Add the 'openai' package to use API mode."
        ) from exc

    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": build_prompt(data)}],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "marketing_insights",
                    "schema": INSIGHTS_SCHEMA,
                    "strict": True,
                }
            },
        )
    except Exception as exc:
        raise RuntimeError(f"OpenAI API call failed: {exc}") from exc

    raw_text = getattr(response, "output_text", "").strip()
    if not raw_text:
        raise ValueError("OpenAI returned an empty response.")

    return _parse_model_json(raw_text)


def _load_analysis(csv_path: Path) -> dict[str, Any]:
    """Load campaign analysis using the analyzer module."""
    try:
        return load_and_analyze_data(csv_path)
    except TypeError:
        return load_and_analyze_data()


if __name__ == "__main__":
    analysis = _load_analysis(DEFAULT_CSV_PATH)
    insights = generate_insights(analysis)
    print(json.dumps(insights, ensure_ascii=False, indent=2))
