from fastmcp import FastMCP
import os
from typing import Optional
import json
import datetime
from helper import (
    parse_status_param,
    fetch_all_issues,
    get_week_and_month_label,
    parse_date,
    get_member_id,
    parse_tracker_type_param,
    parse_priority_param,
    compact_issues,
    get_project_id,
    fetch_all_users
)

script_dir = os.path.dirname(os.path.abspath(__file__))

members_path = os.path.join(script_dir, "socramine_dict", "members.json")
with open(members_path, "r", encoding="utf-8") as f:
    members = json.load(f)

issue_statuses_path = os.path.join(script_dir, "socramine_dict", "issue_statuses.json")
with open(issue_statuses_path, "r", encoding="utf-8") as f:
    issue_statuses = json.load(f)

priorities_path = os.path.join(script_dir, "socramine_dict", "priorities.json")
with open(priorities_path, "r", encoding="utf-8") as f:
    priorities = json.load(f)

tracker_types_path = os.path.join(script_dir, "socramine_dict", "tracker_types.json")
with open(tracker_types_path, "r", encoding="utf-8") as f:
    tracker_types = json.load(f)

mcp = FastMCP(
    name="ThinkforBL Socramine Server",
    dependencies=["requests"]
)

@mcp.tool()
def get_date_time(format_type: Optional[str] = "datetime") -> str:
    """
    Get the current date and/or time in Seoul timezone (UTC+9).

    IMPORTANT: This function is a pure date/time helper and does NOT provide
    Socramine project data. When answering user questions that require
    Socramine data (for example: hours worked, issues, or estimates), an
    assistant MUST call the appropriate Socramine MCP tool (for example
    `get_hours_per_week_by_date`, `get_issues_per_week_by_date`,
    `get_issues_per_month_by_date`, `get_hours_per_month_by_date`) to retrieve
    the authoritative data before creating a summary.

    If a user asks for Socramine data but only this date/time tool is
    available, do NOT guess or fabricate numbers. Instead return a concise
    statement that the required Socramine tool is not available and that the
    assistant needs to call the correct MCP tool to answer (for example:
    "I cannot answer that — I need to call `get_hours_per_week_by_date` to
    retrieve Steven's hours for the week"). Use this tool only to obtain
    current date/time values when computing ranges or timestamps.

    Parameters:
    - format_type (str, optional): Format of the returned time. Options:
        * "datetime" (default): Returns full datetime (YYYY-MM-DD HH:MM:SS)
        * "date": Returns only date (YYYY-MM-DD)
        * "time": Returns only time (HH:MM:SS)
        * "iso": Returns ISO format with timezone (YYYY-MM-DDTHH:MM:SS+09:00)

    Returns:
    - str: Current time in Seoul in the requested format.

    Usage examples:
    - get_date_time()
    - get_date_time("date")
    - get_date_time("iso")
    """
    # Seoul timezone is UTC+9
    utc_now = datetime.datetime.utcnow()
    seoul_offset = datetime.timedelta(hours=9)
    now_seoul = utc_now + seoul_offset
    
    if format_type == "date":
        return now_seoul.strftime("%Y-%m-%d")
    elif format_type == "time":
        return now_seoul.strftime("%H:%M:%S")
    elif format_type == "iso":
        return now_seoul.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    else:  # default "datetime"
        return now_seoul.strftime("%Y-%m-%d %H:%M:%S")

@mcp.tool()
def get_issues_per_week_by_date(
    name: str, 
    selected_date: str, 
    status: Optional[str] = '*',
    tracker_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> Optional[list]:
    """
    Get all Redmine issues assigned to a member for the week and month of a given date.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): A concrete date in YYYY-MM-DD format.
      The tool will automatically determine the corresponding week and month.
      Do NOT provide start_date or end_date.
    - status (str, optional): Issue status. Defaults to '*'.
    - tracker_type (str, optional): Tracker type filter.
    - priority (str, optional): Priority filter.

    Returns:
    - list[dict] | None: A compact list of issues for that member, or None if none found.

    Usage examples:
    - get_issues_per_week_by_date(name="Steven", selected_date="2025-08-28")
    - get_issues_per_week_by_date(name="Alice", selected_date="2025-08-01", status="open")
    """
    member_id = get_member_id(name, members)
    status_id = parse_status_param(status, issue_statuses)
    tracker_type_id = parse_tracker_type_param(tracker_type, tracker_types) if tracker_type is not None else None
    priority_id = parse_priority_param(priority, priorities) if priority is not None else None
    date_obj = parse_date(selected_date)
    
    week_label, month_label = get_week_and_month_label(date_obj)
    params = {
        'assigned_to_id': member_id, 
        'cf_38': str(date_obj.year), 
        'cf_41': week_label, 
        'cf_42': month_label, 
    }
    if status_id is not None:
        params['status_id'] = status_id
    if tracker_type_id:
        params['tracker_id'] = tracker_type_id
    if priority_id:
        params['priority_id'] = priority_id
    issues = fetch_all_issues(params)
    return compact_issues(issues) if issues else None

@mcp.tool()
def get_hours_per_week_by_date(
    name: str, 
    selected_date: str, 
    status: Optional[str] = '*',
    tracker_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> float:
    """
    Retrieve the total estimated hours for a member in the week and month of a given date.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): A single date in YYYY-MM-DD format.
      The tool automatically determines the week and month.
      Do NOT provide start_date or end_date.
    - status (str, optional): Issue status. Defaults to '*'.
    - tracker_type (str, optional): Tracker type filter.
    - priority (str, optional): Priority filter.

    Returns:
    - float: Total estimated hours for the member during that week and month.

    Usage examples:
    - get_hours_per_week_by_date(name="Steven", selected_date="2025-08-28")
    """
    member_id = get_member_id(name, members)
    status_id = parse_status_param(status, issue_statuses)
    tracker_type_id = parse_tracker_type_param(tracker_type, tracker_types) if tracker_type is not None else None
    priority_id = parse_priority_param(priority, priorities) if priority is not None else None
    date_obj = parse_date(selected_date)
    
    week_label, month_label = get_week_and_month_label(date_obj)
    params = {
        'assigned_to_id': member_id, 
        'cf_38': str(date_obj.year), 
        'cf_41': week_label, 
        'cf_42': month_label, 
    }
    if status_id is not None:
        params['status_id'] = status_id
    if tracker_type_id:
        params['tracker_id'] = tracker_type_id
    if priority_id:
        params['priority_id'] = priority_id
    issues = fetch_all_issues(params)
    total_hours = 0.0
    for issue in issues:
        try:
            total_hours += float(issue.get("estimated_hours", 0) or 0)
        except ValueError:
            pass
    return total_hours

@mcp.tool()
def get_issues_per_month_by_date(
    name: str, 
    selected_date: str, 
    status: Optional[str] = '*',
    tracker_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> Optional[list]:
    """
    Get all Redmine issues assigned to a member for the month of a given date.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): A concrete date in YYYY-MM-DD format.
      The tool determines the month automatically.
    - status (str, optional): Issue status. Defaults to '*'.
    - tracker_type (str, optional): Tracker type filter.
    - priority (str, optional): Priority filter.

    Returns:
    - list[dict] | None: Compact list of issues, or None if none found.

    Usage example:
    - get_issues_per_month_by_date(name="Steven", selected_date="2025-08-28")
    """
    member_id = get_member_id(name, members)
    status_id = parse_status_param(status, issue_statuses)
    tracker_type_id = parse_tracker_type_param(tracker_type, tracker_types) if tracker_type is not None else None
    priority_id = parse_priority_param(priority, priorities) if priority is not None else None
    date_obj = parse_date(selected_date)
    
    week_label, month_label = get_week_and_month_label(date_obj)
    params = {
        'assigned_to_id': member_id, 
        'cf_38': str(date_obj.year), 
        'cf_42': month_label, 
    }
    if status_id is not None:
        params['status_id'] = status_id
    if tracker_type_id:
        params['tracker_id'] = tracker_type_id
    if priority_id:
        params['priority_id'] = priority_id
    issues = fetch_all_issues(params)
    return compact_issues(issues) if issues else None

@mcp.tool()
def get_hours_per_month_by_date(
    name: str, 
    selected_date: str, 
    status: Optional[str] = '*',
    tracker_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> float:
    """
    Calculate the total estimated hours for a member for the month of a given date.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): Concrete date in YYYY-MM-DD format. 
    - status (str, optional): Issue status. Defaults to '*'.
    - tracker_type (str, optional): Tracker type filter.
    - priority (str, optional): Priority filter.

    Returns:
    - float: Total estimated hours.

    Usage example:
    - get_hours_per_month_by_date(name="Steven", selected_date="2025-08-28")
    """
    member_id = get_member_id(name, members)
    status_id = parse_status_param(status, issue_statuses)
    tracker_type_id = parse_tracker_type_param(tracker_type, tracker_types) if tracker_type is not None else None
    priority_id = parse_priority_param(priority, priorities) if priority is not None else None
    date_obj = parse_date(selected_date)
    
    week_label, month_label = get_week_and_month_label(date_obj)
    params = {
        'assigned_to_id': member_id, 
        'cf_38': str(date_obj.year), 
        'cf_42': month_label, 
    }
    if status_id is not None:
        params['status_id'] = status_id
    if tracker_type_id:
        params['tracker_id'] = tracker_type_id
    if priority_id:
        params['priority_id'] = priority_id
    issues = fetch_all_issues(params)
    total_hours = 0.0
    for issue in issues:
        try:
            total_hours += float(issue.get("estimated_hours", 0) or 0)
        except ValueError:
            pass
    return total_hours

def main():
    """Main entry point for the mcp-socramine package."""
    mcp.run()

if __name__ == "__main__":
    main()