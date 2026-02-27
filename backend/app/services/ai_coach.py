"""AI driving coach: auto-analysis and conversational chat with function calling."""

import json
from openai import AsyncOpenAI

from app.core.config import settings


SYSTEM_PROMPT = """You are an expert motorsport driving coach analyzing telemetry data from track sessions. You help amateur and club-level drivers find more lap time.

Your communication style:
- Be specific and data-driven. Reference exact corner numbers, speeds, and time deltas.
- Prioritize advice by potential time gain (biggest gains first).
- Explain the "why" behind each recommendation so drivers learn, not just follow.
- Use motorsport terminology naturally (trail braking, apex, rotation, understeer, etc.)
- Be encouraging but honest. If the driver is close to the limit, say so.
- When comparing laps, explain what the driver did differently, not just what the numbers say.
- Consider the car's aero configuration when giving advice (aero vs no-aero changes optimal technique).
- Factor in tire condition and weather when assessing performance.
- Estimate time gains in seconds where possible.

You have access to tools that query the session's telemetry data. Use them to answer questions accurately.
When you don't have enough data to answer confidently, say so rather than guessing."""


COACHING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_session_summary",
            "description": "Get an overview of the session: lap times, best lap, track info, weather, car setup.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "The session ID"},
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_lap_comparison",
            "description": "Compare two specific laps side-by-side with corner-by-corner deltas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "lap_a": {"type": "integer", "description": "First lap number"},
                    "lap_b": {"type": "integer", "description": "Second lap number"},
                },
                "required": ["session_id", "lap_a", "lap_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_corner_analysis",
            "description": "Get detailed analysis of a specific corner across multiple laps: entry/min/exit speed, braking point, throttle application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "corner_id": {"type": "integer", "description": "Corner number (1-based)"},
                    "lap_numbers": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Optional list of specific lap numbers. If omitted, uses all valid laps.",
                    },
                },
                "required": ["session_id", "corner_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_speed_trace",
            "description": "Get speed vs distance data for one or more laps for overlay comparison.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "lap_numbers": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Lap numbers to include",
                    },
                },
                "required": ["session_id", "lap_numbers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_consistency_report",
            "description": "Get consistency analysis across laps: overall score, corner-by-corner variation, most/least consistent areas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_braking_zones",
            "description": "Get braking zone data for each corner: braking point, max decel, duration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "lap_number": {"type": "integer", "description": "Specific lap number"},
                },
                "required": ["session_id", "lap_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_conditions",
            "description": "Get weather and track conditions for the session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tire_condition",
            "description": "Get tire condition analysis from photos: wear pattern, compound, remaining life.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_car_setup",
            "description": "Get car setup details from photos: aero configuration, vehicle type, ride height.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gg_diagram",
            "description": "Get lateral vs longitudinal g-force data for friction circle analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "lap_number": {"type": "integer"},
                },
                "required": ["session_id", "lap_number"],
            },
        },
    },
]


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_coaching_report(session_summary: dict) -> dict:
    """Generate an automatic coaching report from session analysis data.

    This is Mode 1 -- called after file upload and analysis, no user question needed.
    """
    client = _get_client()

    prompt = f"""Analyze this motorsport session data and provide a coaching report.

Session Data:
{json.dumps(session_summary, indent=2)}

Provide your response as a JSON object with:
- "summary": 2-3 sentence overall assessment
- "recommendations": array of objects with:
  - "priority": "HIGH", "MEDIUM", or "LOW"
  - "category": "braking", "throttle", "line", "consistency", "setup", or "general"
  - "corner_id": corner number or null if general
  - "description": specific, actionable advice
  - "estimated_gain_s": estimated time gain in seconds, or null
- "overall_assessment": 1-2 sentence motivational summary with the key takeaway

Focus on the biggest time gains first. Be specific about corner numbers and measurable improvements."""

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "summary": text,
            "recommendations": [],
            "overall_assessment": "Unable to parse structured report.",
        }


async def generate_comparison_coaching(comparison_data: dict) -> dict:
    """Generate AI coaching analysis explaining why one lap is faster than another.

    Takes the full comparison result (delta trace summary, corner-by-corner breakdown)
    and produces actionable coaching insights.
    """
    client = _get_client()

    # Summarize the delta trace to key sections instead of sending all 500 points
    trace = comparison_data.get("delta_trace", [])
    trace_summary = []
    if trace:
        for i in range(0, len(trace), max(1, len(trace) // 20)):
            pt = trace[i]
            trace_summary.append({
                "distance_m": pt["distance_m"],
                "delta_s": pt["time_delta_s"],
                "speed_diff_mph": pt["speed_diff_mph"],
            })

    coaching_data = {
        "lap_a": comparison_data.get("lap_a"),
        "lap_b": comparison_data.get("lap_b"),
        "lap_a_time_s": comparison_data.get("lap_a_time_s"),
        "lap_b_time_s": comparison_data.get("lap_b_time_s"),
        "total_delta_s": comparison_data.get("total_delta_s"),
        "session_a_name": comparison_data.get("session_a_name"),
        "session_b_name": comparison_data.get("session_b_name"),
        "session_a_date": comparison_data.get("session_a_date"),
        "session_b_date": comparison_data.get("session_b_date"),
        "corner_deltas": comparison_data.get("corner_deltas", []),
        "delta_trace_sampled": trace_summary,
        "biggest_loss_corner": comparison_data.get("biggest_loss_corner"),
        "biggest_gain_corner": comparison_data.get("biggest_gain_corner"),
    }

    is_cross = bool(comparison_data.get("session_a_name"))

    prompt = f"""Analyze this lap comparison data and provide coaching insights explaining why one lap is faster than the other. {"These laps are from different sessions, so also consider how conditions or driver progression may factor in." if is_cross else ""}

All speeds are in mph. Lap A is the reference (typically faster). Positive delta means Lap B is slower.

Comparison Data:
{json.dumps(coaching_data, indent=2)}

Provide your response as a JSON object with:
- "headline": One sentence summary (e.g. "Lap 3 is 0.8s faster, mainly gained through Turn 9 and Turn 10")
- "key_findings": Array of 3-5 most important findings, each with:
  - "corner_label": Which corner or section (use the corner_label from data, or "Overall" / "Straight" for non-corner sections)
  - "finding": What happened (e.g. "Braked 15 ft later and carried 4 mph more through the apex")
  - "impact": "positive" (faster lap did this well) or "negative" (slower lap lost time here)
  - "time_impact_s": Approximate time gained or lost at this section
  - "advice": Actionable coaching advice for the driver
- "progression_notes": If cross-session, 1-2 sentences about driver improvement over time. If same session, notes about tire degradation or consistency. Can be null.
- "action_items": Array of 2-3 concrete things to work on next session, ordered by priority

Focus on practical, actionable insights. Reference specific speeds and corner names."""

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "headline": text[:200],
            "key_findings": [],
            "progression_notes": None,
            "action_items": [],
        }


async def chat_with_coach(
    session_id: str,
    user_message: str,
    conversation_history: list[dict],
    session_context: dict,
    tool_executor,
) -> dict:
    """Handle a conversational chat message with function calling.

    This is Mode 2 -- the driver asks a question and the AI coach answers
    using tool calls to query specific data.

    Args:
        session_id: The session being discussed
        user_message: The driver's question
        conversation_history: Previous messages in the conversation
        session_context: Brief session metadata for the system prompt
        tool_executor: Async callable that executes tool functions and returns results
    """
    client = _get_client()

    context_str = json.dumps(session_context, indent=2)
    system = (
        f"{SYSTEM_PROMPT}\n\n"
        f"You are currently analyzing session {session_id}.\n"
        f"Session context:\n{context_str}\n\n"
        f"Use the available tools to query specific data before answering. "
        f"Don't guess -- look up the data."
    )

    messages = [{"role": "system", "content": system}]
    for msg in conversation_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    tool_calls_made = []
    max_rounds = 5

    for _ in range(max_rounds):
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=COACHING_TOOLS,
            tool_choice="auto",
            temperature=0.4,
            max_tokens=1500,
        )

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" or (
            choice.message.tool_calls and len(choice.message.tool_calls) > 0
        ):
            messages.append(choice.message)

            for tc in choice.message.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)
                tool_calls_made.append(fn_name)

                result = await tool_executor(fn_name, fn_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })
        else:
            return {
                "message": choice.message.content or "",
                "tool_calls_made": tool_calls_made,
            }

    last = response.choices[0].message.content or "I wasn't able to fully analyze that. Could you try rephrasing?"
    return {"message": last, "tool_calls_made": tool_calls_made}
