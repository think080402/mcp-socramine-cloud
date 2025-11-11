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

@mcp.tool()
def get_issues(
    name: str,
    project: Optional[str] = None,
    start_date: Optional[str] = None,
    due_date: Optional[str] = None,
    status: Optional[str] = '*',
    tracker_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> Optional[list]:
    """
    Get all Redmine issues assigned to a member with flexible filtering options.

    Parameters:
    - name (str): Member name (required).
    - project (str, optional): Project name filter.
    - start_date (str, optional): Start date filter in YYYY-MM-DD format.
    - due_date (str, optional): Due date filter in YYYY-MM-DD format.
    - status (str, optional): Issue status. Defaults to '*'.
    - tracker_type (str, optional): Tracker type filter.
    - priority (str, optional): Priority filter.

    Returns:
    - list[dict] | None: Compact list of issues, or None if none found.

    Usage examples:
    - get_issues(name="Steven")
    - get_issues(name="Alice", status="open", tracker_type="Bug")
    - get_issues(name="Bob", project="ProjectX", start_date="2025-01-01", due_date="2025-12-31")
    """
    member_id = get_member_id(name, members)
    project_id = get_project_id(project) if project is not None else None
    status_id = parse_status_param(status, issue_statuses)
    tracker_type_id = parse_tracker_type_param(tracker_type, tracker_types) if tracker_type is not None else None
    priority_id = parse_priority_param(priority, priorities) if priority is not None else None
    params = {'assigned_to_id': member_id, 'cf_38': str(datetime.datetime.now().year)}
    if project_id:
        params['project_id'] = project_id
    if start_date:
        params['start_date'] = start_date
    if due_date:
        params['due_date'] = due_date
    if status_id is not None:
        params['status_id'] = status_id
    if tracker_type_id:
        params['tracker_id'] = tracker_type_id
    if priority_id:
        params['priority_id'] = priority_id
    issues = fetch_all_issues(params)
    return compact_issues(issues) if issues else None

# Compy
@mcp.tool()
def get_this_month_compy_issues_by_date(
    name: str, 
    selected_date: str, 
    status: Optional[str] = '*',
    priority: Optional[str] = None,
) -> Optional[list]:
    """
    Get all 'compy' issues (tracker_id=7) assigned to a member for the month of a given date.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): Concrete date in YYYY-MM-DD format.
      The tool determines the month automatically.
    - status (str, optional): Issue status. Defaults to '*'.
    - priority (str, optional): Priority filter.

    Returns:
    - list[dict] | None: Compact list of compy issues, or None if none found.

    Usage examples:
    - get_this_month_compy_issues_by_date(name="Alice", selected_date="2025-08-28")
    - get_this_month_compy_issues_by_date(name="Steven", selected_date="2025-11-11", status="open")
    """
    member_id = get_member_id(name, members)
    status_id = parse_status_param(status, issue_statuses)
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
    if priority_id:
        params['priority_id'] = priority_id
    params['tracker_id'] = '7'
    issues = fetch_all_issues(params)
    return compact_issues(issues) if issues else None

@mcp.tool()
def get_this_month_compy_hour_by_date(
    name: str, 
    selected_date: str, 
    status: Optional[str] = '*',
    priority: Optional[str] = None,
) -> float:
    """
    Calculate the total estimated hours for 'compy' issues (tracker_id=7) 
    assigned to a member for the month of a given date.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): Concrete date in YYYY-MM-DD format.
      The tool determines the month automatically.
    - status (str, optional): Issue status. Defaults to '*'.
    - priority (str, optional): Priority filter.

    Returns:
    - float: Total estimated hours for compy issues.

    Usage examples:
    - get_this_month_compy_hour_by_date(name="Steven", selected_date="2025-08-28")
    - get_this_month_compy_hour_by_date(name="Alice", selected_date="2025-11-11", status="open")
    """
    member_id = get_member_id(name, members)
    status_id = parse_status_param(status, issue_statuses)
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
    if priority_id:
        params['priority_id'] = priority_id
    params['tracker_id'] = '7'
    issues = fetch_all_issues(params)
    total_hours = 0.0
    for issue in issues:
        try:
            total_hours += float(issue.get("estimated_hours", 0) or 0)
        except ValueError:
            pass
    return total_hours

@mcp.tool()
def get_this_year_compy_issues_by_date(
    name: str, 
    selected_date: str, 
    status: Optional[str] = '*',
    priority: Optional[str] = None,
) -> Optional[list]:
    """
    Get all 'compy' issues (tracker_id=7) assigned to a member for the year of a given date.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): Concrete date in YYYY-MM-DD format.
      The tool determines the year automatically.
    - status (str, optional): Issue status. Defaults to '*'.
    - priority (str, optional): Priority filter.

    Returns:
    - list[dict] | None: Compact list of compy issues, or None if none found.

    Usage examples:
    - get_this_year_compy_issues_by_date(name="Steven", selected_date="2025-08-28")
    - get_this_year_compy_issues_by_date(name="Bob", selected_date="2025-11-11", status="closed")
    """
    member_id = get_member_id(name, members)
    status_id = parse_status_param(status, issue_statuses)
    priority_id = parse_priority_param(priority, priorities) if priority is not None else None
    date_obj = parse_date(selected_date)
    
    params = {
        'assigned_to_id': member_id, 
        'cf_38': str(date_obj.year)
    }
    if status_id is not None:
        params['status_id'] = status_id
    if priority_id:
        params['priority_id'] = priority_id
    params['tracker_id'] = '7'
    issues = fetch_all_issues(params)
    return compact_issues(issues) if issues else None

@mcp.tool()
def get_this_year_compy_hour_by_date(
    name: str, 
    selected_date: str, 
    status: Optional[str] = '*',
    priority: Optional[str] = None,
) -> float:
    """
    Calculate the total estimated hours for 'compy' issues (tracker_id=7) 
    assigned to a member for the year of a given date.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): Concrete date in YYYY-MM-DD format.
      The tool determines the year automatically.
    - status (str, optional): Issue status. Defaults to '*'.
    - priority (str, optional): Priority filter.

    Returns:
    - float: Total estimated hours for compy issues.

    Usage examples:
    - get_this_year_compy_hour_by_date(name="Alice", selected_date="2025-08-28")
    - get_this_year_compy_hour_by_date(name="Steven", selected_date="2025-11-11", status="open")
    """
    member_id = get_member_id(name, members)
    status_id = parse_status_param(status, issue_statuses)
    priority_id = parse_priority_param(priority, priorities) if priority is not None else None
    date_obj = parse_date(selected_date)
    
    params = {
        'assigned_to_id': member_id, 
        'cf_38': str(date_obj.year)
    }
    if status_id is not None:
        params['status_id'] = status_id
    if priority_id:
        params['priority_id'] = priority_id
    params['tracker_id'] = '7'
    issues = fetch_all_issues(params)
    total_hours = 0.0
    for issue in issues:
        try:
            total_hours += float(issue.get("estimated_hours", 0) or 0)
        except ValueError:
            pass
    return total_hours

# Performance
@mcp.tool()
def get_this_month_performance_hour_ev(
    name: str
) -> dict:
    """
    Calculate the total estimated hours and EV (earned value) for completed issues 
    assigned to a member during the current month.

    This retrieves completed issues (status_id=5) that are due this month,
    excluding child issues and rejected issues (cf_19='반려'), and only
    includes issues with a non-null cf_17 value.

    Parameters:
    - name (str): Member name (required).

    Returns:
    - dict: {"total_hours": float, "total_ev": float}

    Usage example:
    - get_this_month_performance_hour_ev(name="Steven")
    """
    member_id = get_member_id(name, members)
    params = {
        'assigned_to_id': member_id,
        'status_id': '5',  # status_id=5 (완료)
        'due_date': 'm',   # due this month
        'child_id': '!*',  # no child
        'cf_19': '!반려',   # cf_19 != 반려 (not rejected)
        'cf_17': '!*',     # cf_17 is not null
    }
    issues = fetch_all_issues(params)
    total_hours = 0.0
    total_ev = 0.0
    for issue in issues:
        try:
            total_hours += float(issue.get("estimated_hours", 0) or 0)
        except ValueError:
            pass
        # Find EV in custom_fields
        for cf in issue.get("custom_fields", []):
            if cf.get("name") == "EV":
                try:
                    total_ev += float(cf.get("value", 0) or 0)
                except ValueError:
                    pass
    return {"total_hours": total_hours, "total_ev": total_ev}

@mcp.tool()
def get_this_year_performance_hour_ev(
    name: str
) -> dict:
    """
    Calculate the total estimated hours and EV (earned value) for completed issues 
    assigned to a member during the current year.

    This retrieves completed issues (status_id=5) that are due this year,
    excluding child issues and rejected issues (cf_19='반려'), and only
    includes issues with a non-null cf_17 value.

    Parameters:
    - name (str): Member name (required).

    Returns:
    - dict: {"total_hours": float, "total_ev": float}

    Usage example:
    - get_this_year_performance_hour_ev(name="Alice")
    """
    member_id = get_member_id(name, members)
    
    params = {
        'assigned_to_id': member_id,
        'status_id': '5',   # status_id=5 (완료)
        'due_date': 'y',    # due this year
        'child_id': '!*',   # no child
        'cf_19': '!반려',    # cf_19 != 반려 (not rejected)
        'cf_17': '!*',      # cf_17 is not null
    }
    issues = fetch_all_issues(params)
    total_hours = 0.0
    total_ev = 0.0
    for issue in issues:
        try:
            total_hours += float(issue.get("estimated_hours", 0) or 0)
        except ValueError:
            pass
        # Find EV in custom_fields
        for cf in issue.get("custom_fields", []):
            if cf.get("name") == "EV":
                try:
                    total_ev += float(cf.get("value", 0) or 0)
                except ValueError:
                    pass
    return {"total_hours": total_hours, "total_ev": total_ev}

@mcp.tool()
def get_all_users() -> Optional[list]:
    """
    Retrieve all users from Redmine.

    This function fetches the complete list of users available in the Redmine system.

    Returns:
    - list[dict] | None: List of user objects with their details, or None if no users found.

    Usage example:
    - get_all_users()
    """
    users = fetch_all_users()
    return users if users else None

def main():
    """Main entry point for the mcp-socramine package."""
    mcp.run()

if __name__ == "__main__":
    main()