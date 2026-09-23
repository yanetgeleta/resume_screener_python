# get the text for the resume that made it in top N and extract the skills and experience years using gpt oss 120 with groq


import json
import logging

import groq
from pydantic import BaseModel, ConfigDict

from jobs import groq_client

logger = logging.getLogger(__name__)


class SkillsAndExperienceYears(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: list[str]
    experience_years: int | None


def extract_skills_experience(
    system_content: str, user_content: str
) -> SkillsAndExperienceYears:
    """Returns skills and experience years in json format with pydantic adherence"""
    last_error = None
    sanitized_text = user_content[:12000]

    client = groq_client.groq_client_instance
    try:
        llm_response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": sanitized_text},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "skills_and_experience_years_extraction",
                    "strict": True,
                    "schema": SkillsAndExperienceYears.model_json_schema(),
                },
            },
            temperature=0.0,
            max_tokens=2048,
        )

        raw_result = json.loads(llm_response.choices[0].message.content or "{}")
        result = SkillsAndExperienceYears.model_validate(raw_result)
        return result
    except (groq.GroqError, json.JSONDecodeError) as exc:
        logger.warning(
            "Extraction failed on Openai 120b: %s. Trying fallback model.",
            exc,
        )
        last_error = exc
    raise last_error
