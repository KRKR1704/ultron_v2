"""
tools/calendar_tasks.py — Google Calendar API + Tasks integration.

Uses dateparser for natural language time expressions.
All methods return human-readable strings for Ultron to speak.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import dateparser
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
_TOKEN_PATH = "./token.json"
_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]


def _get_credentials():
    """Load or refresh Google OAuth2 credentials."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request

        creds = None

        if os.path.exists(_TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(_TOKEN_PATH, _SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif os.path.exists(_CREDENTIALS_PATH):
                flow = InstalledAppFlow.from_client_secrets_file(
                    _CREDENTIALS_PATH, _SCOPES
                )
                creds = flow.run_local_server(port=0)
                with open(_TOKEN_PATH, "w") as token:
                    token.write(creds.to_json())
            else:
                return None

        return creds

    except Exception as err:
        log.error("Google credentials error: %s", err)
        return None


def _calendar_service():
    creds = _get_credentials()
    if not creds:
        return None
    try:
        from googleapiclient.discovery import build
        return build("calendar", "v3", credentials=creds)
    except Exception as err:
        log.error("Calendar service build failed: %s", err)
        return None


def _tasks_service():
    creds = _get_credentials()
    if not creds:
        return None
    try:
        from googleapiclient.discovery import build
        return build("tasks", "v1", credentials=creds)
    except Exception as err:
        log.error("Tasks service build failed: %s", err)
        return None


def _parse_time(time_str: str) -> Optional[datetime]:
    """Parse a natural language time string using dateparser."""
    if not time_str:
        return None
    try:
        result = dateparser.parse(
            time_str,
            settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": True},
        )
        return result
    except Exception:
        return None


class CalendarTasks:

    # ── Calendar ──────────────────────────────────────────────────────────────

    async def list_events(self, days_ahead: int = 7) -> str:
        service = _calendar_service()
        if not service:
            return "Google Calendar is not configured. Please set up OAuth2 credentials."

        try:
            now = datetime.now(timezone.utc)
            end = now + timedelta(days=days_ahead)

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=now.isoformat(),
                    timeMax=end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=10,
                )
                .execute()
            )

            events = events_result.get("items", [])
            if not events:
                return f"You have no upcoming events in the next {days_ahead} days."

            lines = [f"Your next {len(events)} events:\n"]
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date", ""))
                title = event.get("summary", "(No title)")
                try:
                    dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    time_str = dt.strftime("%A, %B %d at %I:%M %p")
                except Exception:
                    time_str = start
                lines.append(f"- {time_str}: {title}")

            return "\n".join(lines)

        except Exception as err:
            log.error("list_events failed: %s", err)
            return f"Could not retrieve calendar events: {err}"

    async def create_event(
        self,
        title: str,
        start_str: str,
        end_str: Optional[str] = None,
        description: str = "",
    ) -> str:
        service = _calendar_service()
        if not service:
            return "Google Calendar is not configured."

        start_dt = _parse_time(start_str)
        if not start_dt:
            return f"I couldn't understand the time: '{start_str}'"

        if end_str:
            end_dt = _parse_time(end_str)
        else:
            end_dt = start_dt + timedelta(hours=1)

        try:
            event = {
                "summary": title,
                "description": description,
                "start": {"dateTime": start_dt.isoformat()},
                "end": {"dateTime": end_dt.isoformat()},
            }
            created = service.events().insert(calendarId="primary", body=event).execute()
            time_display = start_dt.strftime("%A, %B %d at %I:%M %p")
            return f"Event '{title}' created for {time_display}."

        except Exception as err:
            log.error("create_event failed: %s", err)
            return f"Could not create event: {err}"

    async def handle_calendar(self, command: str) -> str:
        """Parse a natural language calendar command and execute it."""
        lower = command.lower()

        if any(w in lower for w in ["list", "show", "what", "upcoming", "schedule"]):
            return await self.list_events()

        if any(w in lower for w in ["create", "add", "schedule", "book", "set up"]):
            # Very simple extraction — LLM has already classified this as calendar intent
            # Pass full command as title; prompt_manager + brain will handle details
            return await self.create_event(
                title=command,
                start_str="tomorrow at 9am",
            )

        return await self.list_events()

    # ── Tasks ─────────────────────────────────────────────────────────────────

    async def list_tasks(self) -> str:
        service = _tasks_service()
        if not service:
            return "Google Tasks is not configured."

        try:
            result = service.tasks().list(tasklist="@default", maxResults=20).execute()
            tasks = result.get("items", [])
            if not tasks:
                return "You have no pending tasks."

            lines = [f"Your tasks ({len(tasks)} total):\n"]
            for task in tasks:
                status = "✓" if task.get("status") == "completed" else "○"
                title = task.get("title", "(No title)")
                due = task.get("due", "")
                due_str = f" (due {due[:10]})" if due else ""
                lines.append(f"{status} {title}{due_str}")

            return "\n".join(lines)

        except Exception as err:
            log.error("list_tasks failed: %s", err)
            return f"Could not retrieve tasks: {err}"

    async def create_task(self, title: str, due_str: str = "") -> str:
        service = _tasks_service()
        if not service:
            return "Google Tasks is not configured."

        try:
            task_body: dict[str, Any] = {"title": title}

            if due_str:
                due_dt = _parse_time(due_str)
                if due_dt:
                    task_body["due"] = due_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            service.tasks().insert(tasklist="@default", body=task_body).execute()
            return f"Task '{title}' added to your list."

        except Exception as err:
            log.error("create_task failed: %s", err)
            return f"Could not create task: {err}"

    async def complete_task(self, task_title: str) -> str:
        service = _tasks_service()
        if not service:
            return "Google Tasks is not configured."

        try:
            result = service.tasks().list(tasklist="@default").execute()
            tasks = result.get("items", [])

            task_id = None
            for task in tasks:
                if task_title.lower() in task.get("title", "").lower():
                    task_id = task["id"]
                    break

            if not task_id:
                return f"Could not find a task matching '{task_title}'."

            service.tasks().patch(
                tasklist="@default",
                task=task_id,
                body={"status": "completed"},
            ).execute()
            return f"Task '{task_title}' marked as complete."

        except Exception as err:
            log.error("complete_task failed: %s", err)
            return f"Could not complete task: {err}"

    async def handle_tasks(self, command: str) -> str:
        """Parse a natural language task command and execute it."""
        lower = command.lower()

        if any(w in lower for w in ["list", "show", "what", "all"]):
            return await self.list_tasks()

        if any(w in lower for w in ["complete", "finish", "done", "mark"]):
            # Extract task name after the verb
            import re
            match = re.search(
                r"(?:complete|finish|done|mark)[:\s]+(.+?)(?:\s+as)?$",
                lower,
            )
            title = match.group(1).strip() if match else command
            return await self.complete_task(title)

        if any(w in lower for w in ["add", "create", "remind", "new"]):
            import re
            match = re.search(
                r"(?:add|create|remind me to|new)[:\s]+(.+)", lower
            )
            title = match.group(1).strip() if match else command
            return await self.create_task(title)

        return await self.list_tasks()


# ── Module-level singleton ────────────────────────────────────────────────────
calendar_tasks = CalendarTasks()
