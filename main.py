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
    fetch_all_users,
    fetch_all_projects
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

# Date and Time
@mcp.tool()
def get_date_time(format_type: Optional[str] = "datetime") -> str:
    """
    Get the current date and/or time in Seoul timezone (UTC+9).
    
    Use this tool when you need to determine the current date for date-based queries.
    For example, when a user asks about "this week", "this month", "today", or "now",
    call this tool first to get the current date, then use it with other Socramine tools.

    IMPORTANT: This is a date/time helper only. After getting the current date, you MUST
    call the appropriate Socramine data tools (like `get_hours_per_week_by_date`,
    `get_issues_per_month_by_date`, etc.) to retrieve actual project data. Do NOT
    fabricate or guess data values.

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

# Weekly and Monthly Issues and Hours
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
    
    Note: "Issues" in Redmine can be referred to as tasks, work items, or todos.
    Use this tool when users ask about any of these terms.
    
    **IMPORTANT: Use this tool for weekly agreement status checks.**
    Each issue includes an "agreed" field:
    - agreed=true: The task is agreed (no agreement needed)
    - agreed=false: The task needs agreement (has content in '합의필요사항')
    
    When users ask about "agreed tasks this week" or "is all tasks agreed", use this tool
    and check the "agreed" field in the results.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): A concrete date in YYYY-MM-DD format.
      The tool will automatically determine the corresponding week and month.
      Do NOT provide start_date or end_date.
    - status (str, optional): Issue status. Valid values: '신규', '진행 중', '검수대기', 
      '승인대기', '완료됨', '반려됨', '계획 수립 필요', '계획 검토 필요(진행 중)', '보류됨', 
      '완료요청', '구현됨', or '*' for all statuses. Defaults to '*'.
    - tracker_type (str, optional): Tracker type filter.
    - priority (str, optional): Priority filter.

    Returns:
    - list[dict] | None: A compact list of issues for that member with "agreed" field, 
      or None if none found.

    Usage examples:
    - get_issues_per_week_by_date(name="Steven", selected_date="2025-08-28")
    - get_issues_per_week_by_date(name="Alice", selected_date="2025-08-01", status="*")
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
    - status (str, optional): Issue status. Valid values: '신규', '진행 중', '검수대기', 
      '승인대기', '완료됨', '반려됨', '계획 수립 필요', '계획 검토 필요(진행 중)', '보류됨', 
      '완료요청', '구현됨', or '*' for all statuses. Defaults to '*'.
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
    
    Note: "Issues" can also be called tasks, work items, or todos.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): A concrete date in YYYY-MM-DD format.
      The tool determines the month automatically.
    - status (str, optional): Issue status. Valid values: '신규', '진행 중', '검수대기', 
      '승인대기', '완료됨', '반려됨', '계획 수립 필요', '계획 검토 필요(진행 중)', '보류됨', 
      '완료요청', '구현됨', or '*' for all statuses. Defaults to '*'.
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
    - status (str, optional): Issue status. Valid values: '신규', '진행 중', '검수대기', 
      '승인대기', '완료됨', '반려됨', '계획 수립 필요', '계획 검토 필요(진행 중)', '보류됨', 
      '완료요청', '구현됨', or '*' for all statuses. Defaults to '*'.
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

# General Issues
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
    
    Note: In Redmine, "issues" may be referred to as tasks, work items, todos,
    or assignments. Use this tool for any of these terms.

    Parameters:
    - name (str): Member name (required).
    - project (str, optional): Project name filter.
    - start_date (str, optional): Start date filter in YYYY-MM-DD format.
    - due_date (str, optional): Due date filter in YYYY-MM-DD format.
    - status (str, optional): Issue status. Valid values: '신규', '진행 중', '검수대기', 
      '승인대기', '완료됨', '반려됨', '계획 수립 필요', '계획 검토 필요(진행 중)', '보류됨', 
      '완료요청', '구현됨', or '*' for all statuses. Defaults to '*'.
    - tracker_type (str, optional): Tracker type filter.
    - priority (str, optional): Priority filter.

    Returns:
    - list[dict] | None: Compact list of issues, or None if none found.

    Usage examples:
    - get_issues(name="Steven")
    - get_issues(name="Alice", status="*", tracker_type="Bug")
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
    
    Note: "Issues" can also be referred to as tasks, work items, or todos.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): Concrete date in YYYY-MM-DD format.
      The tool determines the month automatically.
    - status (str, optional): Issue status. Valid values: '신규', '진행 중', '검수대기', 
      '승인대기', '완료됨', '반려됨', '계획 수립 필요', '계획 검토 필요(진행 중)', '보류됨', 
      '완료요청', '구현됨', or '*' for all statuses. Defaults to '*'.
    - priority (str, optional): Priority filter.

    Returns:
    - list[dict] | None: Compact list of compy issues, or None if none found.

    Usage examples:
    - get_this_month_compy_issues_by_date(name="Alice", selected_date="2025-08-28")
    - get_this_month_compy_issues_by_date(name="Steven", selected_date="2025-11-11", status="*")
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
    - status (str, optional): Issue status. Valid values: '신규', '진행 중', '검수대기', 
      '승인대기', '완료됨', '반려됨', '계획 수립 필요', '계획 검토 필요(진행 중)', '보류됨', 
      '완료요청', '구현됨', or '*' for all statuses. Defaults to '*'.
    - priority (str, optional): Priority filter.

    Returns:
    - float: Total estimated hours for compy issues.

    Usage examples:
    - get_this_month_compy_hour_by_date(name="Steven", selected_date="2025-08-28")
    - get_this_month_compy_hour_by_date(name="Alice", selected_date="2025-11-11", status="*")
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
    
    Note: "Issues" can also be referred to as tasks, work items, or todos.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): Concrete date in YYYY-MM-DD format.
      The tool determines the year automatically.
    - status (str, optional): Issue status. Valid values: '신규', '진행 중', '검수대기', 
      '승인대기', '완료됨', '반려됨', '계획 수립 필요', '계획 검토 필요(진행 중)', '보류됨', 
      '완료요청', '구현됨', or '*' for all statuses. Defaults to '*'.
    - priority (str, optional): Priority filter.

    Returns:
    - list[dict] | None: Compact list of compy issues, or None if none found.

    Usage examples:
    - get_this_year_compy_issues_by_date(name="Steven", selected_date="2025-08-28")
    - get_this_year_compy_issues_by_date(name="Bob", selected_date="2025-11-11", status="*")
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
    
    Note: When asked for "all employees" or "everyone", first call get_all_users() to get 
    the list of users, then call this function for each user.

    Parameters:
    - name (str): Member name (required).
    - selected_date (str): Concrete date in YYYY-MM-DD format.
      The tool determines the year automatically.
    - status (str, optional): Issue status. Valid values: '신규', '진행 중', '검수대기', 
      '승인대기', '완료됨', '반려됨', '계획 수립 필요', '계획 검토 필요(진행 중)', '보류됨', 
      '완료요청', '구현됨', or '*' for all statuses. Defaults to '*'.
    - priority (str, optional): Priority filter.

    Returns:
    - float: Total estimated hours for compy issues.

    Usage examples:
    - get_this_year_compy_hour_by_date(name="Alice", selected_date="2025-08-28")
    - get_this_year_compy_hour_by_date(name="Steven", selected_date="2025-11-11", status="*")
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

@mcp.tool()
def get_unagreed_compy_issues_by_year(
    selected_date: str,
    name: Optional[str] = None,
    status: Optional[str] = '*',
    priority: Optional[str] = None,
) -> Optional[list]:
    """
    Get all 'compy' issues (tracker_id=7) that are not yet agreed (have '합의필요사항' filled) 
    for the year of a given date. Can filter by a specific member or get for all members.
    
    An issue is considered "not agreed" when it has content in the '합의필요사항' 
    (agreement needed) custom field.

    Note: "Issues" can also be referred to as tasks, work items, or todos.

    Parameters:
    - selected_date (str): Concrete date in YYYY-MM-DD format.
      The tool determines the year automatically.
    - name (str, optional): Member name. If not provided, returns unagreed issues for all members.
    - status (str, optional): Issue status. Valid values: '신규', '진행 중', '검수대기', 
      '승인대기', '완료됨', '반려됨', '계획 수립 필요', '계획 검토 필요(진행 중)', '보류됨', 
      '완료요청', '구현됨', or '*' for all statuses. Defaults to '*'.
    - priority (str, optional): Priority filter.

    Returns:
    - list[dict] | None: Compact list of unagreed compy issues with 'agreed': false, 
      or None if none found.

    Usage examples:
    - get_unagreed_compy_issues_by_year(selected_date="2026-01-07")  # All members
    - get_unagreed_compy_issues_by_year(selected_date="2026-01-07", name="Steven")  # Specific member
    - get_unagreed_compy_issues_by_year(selected_date="2025-08-28", status="진행 중")
    """
    date_obj = parse_date(selected_date)
    status_id = parse_status_param(status, issue_statuses)
    priority_id = parse_priority_param(priority, priorities) if priority is not None else None
    
    params = {
        'cf_38': str(date_obj.year),
        'tracker_id': '7',  # compy
        'cf_18': '*'  # cf_18 is '합의필요사항' - must have value (not agreed)
    }
    
    if name:
        member_id = get_member_id(name, members)
        params['assigned_to_id'] = member_id
    
    if status_id is not None:
        params['status_id'] = status_id
    if priority_id:
        params['priority_id'] = priority_id
    
    issues = fetch_all_issues(params)
    return compact_issues(issues) if issues else None

# Performance
@mcp.tool()
def get_this_month_performance_issues_ev(
    name: str
) -> Optional[list]:
    """
    Get all completed performance issues with EV assigned to a member during the current month.
    
    Note: "Issues" can also be called tasks, work items, todos, or completed work.

    This retrieves completed issues (status_id=5) that are due this month,
    excluding child issues and rejected issues (cf_19='반려'), and only
    includes issues with a non-null cf_17 (EV) value.

    Parameters:
    - name (str): Member name (required).

    Returns:
    - list[dict] | None: Compact list of performance issues with EV, or None if none found.

    Usage example:
    - get_this_month_performance_issues_ev(name="Steven")
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
    return compact_issues(issues) if issues else None

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
def get_this_year_performance_issues_ev(
    name: str
) -> Optional[list]:
    """
    Get all completed performance issues with EV assigned to a member during the current year.
    
    Note: "Issues" can also be called tasks, work items, todos, or completed work.

    This retrieves completed issues (status_id=5) that are due this year,
    excluding child issues and rejected issues (cf_19='반려'), and only
    includes issues with a non-null cf_17 (EV) value.

    Parameters:
    - name (str): Member name (required).

    Returns:
    - list[dict] | None: Compact list of performance issues with EV, or None if none found.

    Usage example:
    - get_this_year_performance_issues_ev(name="Alice")
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
    return compact_issues(issues) if issues else None

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

# Projects
@mcp.tool()
def get_all_projects() -> Optional[list]:
    """
    Retrieve all leaf projects (innermost child projects) from Redmine.

    This function fetches projects from the Redmine system and filters to return only
    the most inner child projects (leaf projects) - those that don't have any children.
    
    Returns:
    - list[dict] | None: List of leaf project objects with their essential details. Each project object includes:
      * 'id': Project ID
      * 'name': Project name
      * 'identifier': Project identifier (unique key)
      * 'status': Project status
      Returns None if no projects found.

    Usage examples:
    - get_all_projects()
    """
    all_projects = fetch_all_projects()
    if not all_projects:
        return None
    
    # Build a set of all parent project IDs
    parent_ids = set()
    for project in all_projects:
        parent = project.get('parent')
        if parent:
            parent_ids.add(parent.get('id'))
    
    # Filter to only leaf projects (projects that are not parents)
    leaf_projects = [p for p in all_projects if p.get('id') not in parent_ids]
    
    # Return only essential fields to avoid context length issues
    # Removed description field as it can be very long
    compact_projects = [
        {
            'id': p.get('id'),
            'name': p.get('name'),
            'identifier': p.get('identifier'),
            'status': p.get('status')
        }
        for p in leaf_projects
    ]
    
    return compact_projects if compact_projects else None


@mcp.tool()
def get_delayed_tasks_by_project(project: str) -> Optional[dict]:
    """
    Get all delayed tasks in a specific project with total estimated hours.
    
    A task is considered delayed if:
    - It has a due date that is in the past (before today)
    - It has status '신규' (new) or '진행 중' (in progress)
    
    Note: "Tasks" in Redmine can be referred to as issues, work items, or todos.

    Parameters:
    - project (str): Project name or identifier (required).

    Returns:
    - dict | None: A dictionary containing:
      * 'tasks': Compact list of delayed tasks
      * 'total_hours': Total estimated hours of all delayed tasks
      * 'task_count': Number of delayed tasks
      Each task includes:
      * 'id': Task ID
      * 'subject': Task subject/title
      * 'status': Current status
      * 'due_date': Original due date
      * 'assigned_to': Person assigned to the task
      * 'estimated_hours': Estimated hours for this task
      Returns None if no delayed tasks found.

    Usage examples:
    - get_delayed_tasks_by_project(project="My Project")
    - get_delayed_tasks_by_project(project="project-identifier")
    """
    project_id = get_project_id(project)
    
    # Get current date in Seoul timezone
    utc_now = datetime.datetime.utcnow()
    seoul_offset = datetime.timedelta(hours=9)
    today = (utc_now + seoul_offset).date()
    
    # Fetch issues with status '신규' (1) or '진행 중' (2)
    # These are the only statuses that count as delayed when overdue
    delayed_tasks = []
    
    for status_id in ['1', '2']:  # 1='신규', 2='진행 중'
        params = {
            'project_id': project_id,
            'status_id': status_id
        }
        
        issues = fetch_all_issues(params)
        
        # Filter for tasks with due_date < today
        for issue in issues:
            due_date_str = issue.get('due_date')
            
            if due_date_str:
                try:
                    due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d').date()
                    # Check if overdue
                    if due_date < today:
                        delayed_tasks.append(issue)
                except ValueError:
                    # Skip issues with invalid date format
                    pass
    
    if not delayed_tasks:
        return None
    
    # Calculate total hours
    total_hours = 0.0
    for task in delayed_tasks:
        total_hours += float(task.get("estimated_hours", 0) or 0)
    
    return {
        "tasks": compact_issues(delayed_tasks),
        "total_hours": total_hours,
        "task_count": len(delayed_tasks)
    }


@mcp.tool()
def get_all_projects_with_delayed_tasks() -> Optional[list]:
    """
    Get all projects that have delayed tasks, with task count and total hours for each.
    
    A task is considered delayed if:
    - It has a due date that is in the past (before today)
    - It has status '신규' (new) or '진행 중' (in progress)
    
    This is useful for getting an overview of all projects with overdue work.
    
    Returns:
    - list[dict] | None: List of projects with delayed tasks, or None if none found.
      Each entry includes:
      * 'project_id': Project ID
      * 'project_name': Project name
      * 'task_count': Number of delayed tasks
      * 'total_hours': Total estimated hours of delayed tasks
      Returns None if no projects have delayed tasks.

    Usage examples:
    - get_all_projects_with_delayed_tasks()
    """
    # Get current date in Seoul timezone
    utc_now = datetime.datetime.utcnow()
    seoul_offset = datetime.timedelta(hours=9)
    today = (utc_now + seoul_offset).date()
    
    # Fetch ALL delayed tasks across all projects in just 2 API calls
    # This is much faster than querying each project individually
    all_delayed_tasks = []
    
    for status_id in ['1', '2']:  # 1='신규', 2='진행 중'
        params = {
            'status_id': status_id
        }
        
        try:
            issues = fetch_all_issues(params)
            
            # Filter for tasks with due_date < today
            for issue in issues:
                due_date_str = issue.get('due_date')
                
                if due_date_str:
                    try:
                        due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d').date()
                        # Check if overdue
                        if due_date < today:
                            all_delayed_tasks.append(issue)
                    except ValueError:
                        pass
        except Exception:
            continue
    
    if not all_delayed_tasks:
        return None
    
    # Get all projects to build project name lookup
    all_projects = fetch_all_projects()
    if not all_projects:
        return None
    
    # Build project ID to name mapping
    project_map = {p.get('id'): p.get('name') for p in all_projects}
    
    # Build a set of all parent project IDs to identify leaf projects
    parent_ids = set()
    for project in all_projects:
        parent = project.get('parent')
        if parent:
            parent_ids.add(parent.get('id'))
    
    # Group delayed tasks by project
    project_delays = {}
    
    for task in all_delayed_tasks:
        project = task.get('project')
        if not project:
            continue
            
        project_id = project.get('id')
        
        # Only include leaf projects (not parent projects)
        if project_id in parent_ids:
            continue
        
        if project_id not in project_delays:
            project_delays[project_id] = {
                'project_id': project_id,
                'project_name': project_map.get(project_id, 'Unknown'),
                'task_count': 0,
                'total_hours': 0.0
            }
        
        project_delays[project_id]['task_count'] += 1
        project_delays[project_id]['total_hours'] += float(task.get("estimated_hours", 0) or 0)
    
    # Convert to list and sort by project name
    projects_with_delays = sorted(project_delays.values(), key=lambda x: x['project_name'])
    
    return projects_with_delays if projects_with_delays else None


# Users
@mcp.tool()
def get_all_users() -> Optional[list]:
    """
    Retrieve all users from Redmine.

    This function fetches the complete list of users available in the Redmine system.
    
    Use this tool when:
    - User asks for data "for all employees", "for everyone", "for each person", or "for all users"
    - You need to iterate through all team members to collect aggregate data
    - After getting the user list, call other tools (like get_this_year_compy_hour_by_date, 
      get_issues_per_month_by_date, etc.) for each user to gather their individual data

    Returns:
    - list[dict] | None: List of user objects with their details. Each user object includes:
      * 'id': User ID
      * 'login': Username
      * 'firstname': First name
      * 'lastname': Last name
      * 'name': Full name formatted appropriately (auto-generated, use this for other MCP calls)
        - Korean names: "lastname+firstname" (no space)
        - Latin/English names: "lastname firstname" (with space)
      * Other Redmine user fields
      Returns None if no users found.

    Usage examples:
    - get_all_users()
    - When user asks "show compy hours for all employees", call this first, then iterate through 
      each user calling get_this_year_compy_hour_by_date(name=user['name'], ...) for each one
    """
    users = fetch_all_users()
    return users if users else None

def main():
    """Main entry point for the mcp-socramine package."""
    mcp.run()

if __name__ == "__main__":
    main()