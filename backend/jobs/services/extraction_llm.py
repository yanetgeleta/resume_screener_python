# get the text for the resume that made it in top N and extract the skills and experience years using gpt oss 120 with groq


import json

from pydantic import BaseModel, ConfigDict

from jobs import groq_client


class SkillsAndExperienceYears(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: list[str]
    experience_years: int | None


def extract_skills_experience(
    system_content: str, user_content: str
) -> SkillsAndExperienceYears:
    """Returns skills and experience years in json format with pydantic adherence"""

    client = groq_client.groq_client_instance

    llm_response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
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
    )

    raw_result = json.loads(llm_response.choices[0].message.content or "{}")
    result = SkillsAndExperienceYears.model_validate(raw_result)
    return result
