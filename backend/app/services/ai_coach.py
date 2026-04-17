"""AI driving coach: auto-analysis and conversational chat with function calling."""

import json
from openai import AsyncOpenAI

from app.core.config import settings


def _fmt_laptime(seconds: float) -> str:
    """Format seconds into m:ss.sss (e.g. 73.229 -> '1:13.229')."""
    mins = int(seconds // 60)
    secs = seconds % 60
    if mins > 0:
        return f"{mins}:{secs:06.3f}"
    return f"{secs:.3f}s"


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

PROFESSIONAL COACHING ANALYSIS FRAMEWORK:
When analyzing telemetry, evaluate in this priority order:

1. FRICTION CIRCLE UTILIZATION: Is the driver using available grip? Look at g-force utilization %.
   - Below 70% avg utilization = significant grip left on the table
   - Below 50% time above 90% grip = not pushing near the limit in this corner
   - High utilization with low speed = good technique, car may be the limit

2. TRAIL-BRAKING: Is brake release smooth and overlapping with steering input?
   - Overlap % above 40% = good trail-braking technique
   - High smoothness score = progressive brake release (not snapping off the brakes)
   - Low overlap + high entry speed = late apexing without rotation, likely understeering

3. THROTTLE APPLICATION: Is throttle progressive? Any hesitation zones?
   - High application rate = aggressive/binary throttle (may cause oversteer on exit)
   - Long partial throttle time = hesitation or lack of confidence
   - Early throttle-on distance = good corner exit, but only if not causing wheelspin

4. CAR BALANCE (UNDERSTEER/OVERSTEER): Does steering vs yaw rate suggest handling issues?
   - Low yaw-to-steer ratio (< 0.5) = understeer (front pushing, car not rotating)
   - High yaw-to-steer ratio (> 2.0) = oversteer (rear sliding, need to catch)
   - Many post-apex corrections = instability, possibly setup or technique issue

5. TIRE MANAGEMENT: Are wheels locking under braking or spinning on exit?
   - Lockup events = braking too hard or too late, flat-spotting tires
   - Wheelspin events = too much throttle too early, wasting traction
   - High front-rear speed delta = potential drivetrain or slip issue

For each finding, distinguish between:
- DRIVER technique issues (can be fixed with practice)
- CAR setup issues (need mechanical changes — e.g., understeer from spring rates, not driver input)
- At the TIRE LIMIT (driver is already maximizing grip, look elsewhere for time)

Use the get_advanced_corner_analysis tool to access these metrics for specific laps. This provides per-corner friction circle, trail-braking, throttle, steering balance, and wheel slip data.

You have access to tools that query the session's telemetry data. Use them to answer questions accurately.
When you don't have enough data to answer confidently, say so rather than guessing.

IMPORTANT FORMATTING RULES:
- Always express lap times in min:sec.ms format (e.g. 1:13.229, not 73.229s). Never show lap times as raw seconds when they are 60 or above.
- All speeds in your responses MUST be in mph (miles per hour). All tool results provide speeds in mph. Never use kph when communicating with the driver.
- NEVER reference distances in meters or feet. Drivers think in terms of turns and landmarks, not numbers. Always describe locations relative to corners/turns:
  - "Brake later going into Turn 3" NOT "Brake 15m later at 342m"
  - "Get on the gas sooner coming out of Turn 5" NOT "Apply throttle at 528m"
  - "You're losing time between Turn 7 and Turn 8" NOT "Delta increases from 890m to 1020m"
  - "Before Turn 3", "At the apex of Turn 3", "Coming out of Turn 3", "On the straight after Turn 3"
  - Use the corner_label names from the data (e.g. "Turn 3", "Oak Tree", "Thunderbolt") when available.
- ALWAYS use the specific turn number or name. NEVER say vague things like "the big corner", "the fast corner", "in the second half of the lap", or "the hairpin at the end". Always say exactly which turn: "Turn 3", "Turn 7", etc. The driver needs to know EXACTLY which corner you mean.
- When giving plain_english_tips, EVERY tip must include the specific turn number. "Brake later going into Turn 3" is good. "Slow down at the big corner" is NOT acceptable."""


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
    {
        "type": "function",
        "function": {
            "name": "get_advanced_corner_analysis",
            "description": (
                "Get advanced per-corner telemetry metrics for a lap: friction circle utilization "
                "(% of max grip used), trail-braking proficiency score, throttle application analysis "
                "(rate, hesitation, partial throttle time), understeer/oversteer detection "
                "(steering vs yaw rate), and wheel slip analysis (lockup and wheelspin events). "
                "Use this to provide professional-level driving coaching based on rich telemetry data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "lap_number": {"type": "integer", "description": "The lap to analyze"},
                    "corner_id": {
                        "type": "integer",
                        "description": "Optional: specific corner to analyze. Omit for all corners.",
                    },
                },
                "required": ["session_id", "lap_number"],
            },
        },
    },
]


def _format_session_times(data: dict) -> dict:
    """Convert raw seconds fields to m:ss.sss in session data sent to the model."""
    d = dict(data)
    for key in ("best_lap_time_s", "theoretical_best_time_s"):
        if key in d and isinstance(d[key], (int, float)):
            d[key + "_formatted"] = _fmt_laptime(d[key])
    if "laps" in d and isinstance(d["laps"], list):
        d["laps"] = [
            {**lap, "lap_time_formatted": _fmt_laptime(lap["lap_time_s"])}
            if "lap_time_s" in lap else lap
            for lap in d["laps"]
        ]
    return d


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_coaching_report(session_summary: dict) -> dict:
    """Generate an automatic coaching report from session analysis data.

    This is Mode 1 -- called after file upload and analysis, no user question needed.
    """
    client = _get_client()

    formatted_summary = _format_session_times(session_summary)

    prompt = f"""Analyze this motorsport session data and provide a coaching report.

Session Data:
{json.dumps(formatted_summary, indent=2)}

The data may include "advanced_metrics_best_lap" with per-corner telemetry analysis:
- friction_circle: grip utilization % — if low, the driver is leaving grip on the table
- trail_braking: overlap % and smoothness score — higher is better trail-braking technique
- throttle: application rate, hesitation (partial throttle time), throttle-on distance after apex
- steering_balance: understeer/oversteer flags, yaw-to-steer ratio, post-apex corrections
- wheel_slip: lockup and wheelspin events

Use these metrics to provide professional-level coaching. Distinguish between DRIVER technique issues (fixable with practice), CAR setup issues (need mechanical changes), and being AT THE TIRE LIMIT (already maximizing).

CRITICAL: Never reference distances in meters or feet. Always describe locations relative to turn names/numbers (e.g. "going into Turn 3", "coming out of Turn 5", "between Turn 7 and Turn 8").

Provide your response as a JSON object with:
- "summary": 2-3 sentence overall assessment
- "recommendations": array of objects with:
  - "priority": "HIGH", "MEDIUM", or "LOW"
  - "category": "braking", "throttle", "line", "consistency", "setup", "trail_braking", "grip_utilization", "car_balance", or "general"
  - "corner_id": corner number or null if general
  - "description": specific, actionable advice referencing turns, not distances (e.g. "Brake later going into Turn 3" not "Brake 15m later at 342m")
  - "estimated_gain_s": estimated time gain in seconds, or null
- "overall_assessment": 1-2 sentence motivational summary with the key takeaway

Focus on the biggest time gains first. Be specific about turn numbers/names and speeds in mph, never distances in meters or feet."""

    response = await client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_completion_tokens=2000,
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

    lap_a_time = comparison_data.get("lap_a_time_s", 0)
    lap_b_time = comparison_data.get("lap_b_time_s", 0)

    coaching_data = {
        "lap_a": comparison_data.get("lap_a"),
        "lap_b": comparison_data.get("lap_b"),
        "lap_a_time": _fmt_laptime(lap_a_time),
        "lap_b_time": _fmt_laptime(lap_b_time),
        "total_delta_s": comparison_data.get("total_delta_s"),
        "session_a_name": comparison_data.get("session_a_name"),
        "session_b_name": comparison_data.get("session_b_name"),
        "session_a_date": comparison_data.get("session_a_date"),
        "session_b_date": comparison_data.get("session_b_date"),
        "corner_deltas": comparison_data.get("corner_deltas", []),
        "delta_trace_sampled": trace_summary,
        "biggest_loss_corner": comparison_data.get("biggest_loss_corner"),
        "biggest_gain_corner": comparison_data.get("biggest_gain_corner"),
        "advanced_metrics_lap_a": comparison_data.get("advanced_metrics_lap_a"),
        "advanced_metrics_lap_b": comparison_data.get("advanced_metrics_lap_b"),
    }

    is_cross = bool(comparison_data.get("session_a_name"))

    prompt = f"""Analyze this lap comparison data and provide coaching insights explaining why one lap is faster than the other. {"These laps are from different sessions, so also consider how conditions or driver progression may factor in." if is_cross else ""}

All speeds are in mph. Lap A is the reference (typically faster). Positive delta means Lap B is slower.

The data includes "advanced_metrics_lap_a" and "advanced_metrics_lap_b" with per-corner telemetry:
- friction_circle: grip utilization % — compare how much of the tire's capacity each lap uses
- trail_braking: overlap % and smoothness — did the faster lap trail-brake better?
- throttle: application rate, hesitation time — is the faster lap getting on throttle earlier/smoother?
- steering_balance: understeer/oversteer flags — did handling issues cost time?
- wheel_slip: lockup/wheelspin events — did tire abuse cost time?

Use these to explain WHAT the driver did differently and WHY it mattered.

Comparison Data:
{json.dumps(coaching_data, indent=2)}

CRITICAL: Never reference distances in meters or feet. Always describe locations relative to turn names/numbers (e.g. "going into Turn 3", "coming out of Turn 5", "between Turn 7 and Turn 8"). Use the corner_label values from the data.

Provide your response as a JSON object with:
- "headline": One sentence summary (e.g. "Lap 3 is 0.8s faster, mainly gained through Turn 9 and Turn 10")
- "key_findings": Array of 3-5 most important findings, each with:
  - "corner_label": Which corner or section (use the corner_label from data, or "Straight after Turn X" for non-corner sections)
  - "finding": What happened, described relative to turns (e.g. "Braked later going into Turn 3 and carried 4 mph more through the apex")
  - "impact": "positive" (faster lap did this well) or "negative" (slower lap lost time here)
  - "time_impact_s": Approximate time gained or lost at this section
  - "advice": Actionable coaching advice referencing turns, not distances
- "progression_notes": If cross-session, 1-2 sentences about driver improvement over time. If same session, notes about tire degradation or consistency. Can be null.
- "action_items": Array of 2-3 concrete things to work on next session, ordered by priority. Reference turns, not distances.
- "plain_english_tips": Array of 3-6 simple, plain-English tips that any driver can immediately understand — no jargon, no numbers. Each tip is an object with:
  - "tip": A short, punchy instruction that references the turn by name (e.g. "Brake later going into Turn 3", "Get on the gas sooner coming out of Turn 5", "Less sawing at the wheel after the apex in Turn 7 — you're making corrections that slow you down", "You're not using all the grip the tires have at Turn 2 — push harder through the middle of the corner")
  - "why": One sentence explaining what's happening in plain language (e.g. "You're jumping off the brakes before Turn 3 instead of gently easing off — that means the front tires aren't helping you turn", "You're waiting too long to get back on the gas after Turn 5, so you're slow all the way down the straight to Turn 6")
  - "impact": "big" (> 0.2s), "medium" (0.05-0.2s), or "small" (< 0.05s) — how much time this costs

  Write these as if you're standing next to the driver at the track, keeping it casual and encouraging. Use "you" language. Avoid technical terms like "trail braking", "friction circle", "yaw rate" — translate those into what the driver actually DOES with their hands and feet. ALWAYS reference the specific turn name/number.

Focus on practical, actionable insights. Reference specific turns and speeds, never distances in meters or feet."""

    response = await client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_completion_tokens=2000,
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
            model="gpt-5.4",
            messages=messages,
            tools=COACHING_TOOLS,
            tool_choice="auto",
            temperature=0.4,
            max_completion_tokens=1500,
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
