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
    fetch_all_projects,
    get_issue_details,
    get_issue_journals,
    get_issue_children,
    get_issue_parent,
    get_issue_attachments,
    get_all_members_weekly_plan_internal,
    get_all_members_monthly_plan_internal,
    get_all_members_monthly_achievement_internal,
    get_all_members_weekly_achievement_internal,
    get_all_members_ytd_achievement_internal,
    get_members_below_weekly_achievement_threshold_internal
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
    users = fetch_all_users({'status': 1})  # 1 = active users only
    return users if users else None


# Planning Analysis - All Members
@mcp.tool()
def get_all_members_weekly_plan(
    selected_date: str,
    include_unagreed: bool = True
) -> Optional[list]:
    """
    Get planned hours and PV for ALL members for a specific week.
    
    Use this when user asks about "전체 인원" (all personnel), "모든 사람" (everyone), 
    or "팀 전체" (whole team) for weekly planning.
    
    This tool aggregates planning data across all team members, showing:
    - Total planned hours (agreed only or including unagreed)
    - Total PV (Planned Value)
    - Breakdown by agreement status
    
    Parameters:
    - selected_date (str): Date in YYYY-MM-DD format to determine which week.
    - include_unagreed (bool): 
        * True (default): Include both agreed and unagreed tasks
        * False: Only count agreed tasks (합의필요사항 is empty)
    
    Returns:
    - list[dict] | None: List of all members with their planning data:
      * 'name': Member name
      * 'total_hours': Total planned hours (based on include_unagreed setting)
      * 'total_pv': Total PV (based on include_unagreed setting)
      * 'agreed_hours': Hours from agreed tasks only
      * 'agreed_pv': PV from agreed tasks only
      * 'unagreed_hours': Hours from unagreed tasks
      * 'unagreed_pv': PV from unagreed tasks
      Returns None if no users or data found.
    
    Usage examples:
    - get_all_members_weekly_plan(selected_date="2026-01-27", include_unagreed=False)
    - get_all_members_weekly_plan(selected_date="2026-01-27", include_unagreed=True)
    """
    return get_all_members_weekly_plan_internal(selected_date, include_unagreed)


@mcp.tool()
def get_all_members_monthly_plan(
    selected_date: str,
    include_unagreed: bool = True
) -> Optional[list]:
    """
    Get planned hours and PV for ALL members for a specific month.
    
    Use this when user asks about "전체 인원" (all personnel), "모든 사람" (everyone), 
    or "팀 전체" (whole team) for monthly planning.
    
    This tool aggregates planning data across all team members for a full month.
    
    Parameters:
    - selected_date (str): Date in YYYY-MM-DD format to determine which month.
    - include_unagreed (bool): 
        * True (default): Include both agreed and unagreed tasks
        * False: Only count agreed tasks (합의필요사항 is empty)
    
    Returns:
    - list[dict] | None: List of all members with their planning data:
      * 'name': Member name
      * 'total_hours': Total planned hours (based on include_unagreed setting)
      * 'total_pv': Total PV (based on include_unagreed setting)
      * 'agreed_hours': Hours from agreed tasks only
      * 'agreed_pv': PV from agreed tasks only
      * 'unagreed_hours': Hours from unagreed tasks
      * 'unagreed_pv': PV from unagreed tasks
      Returns None if no users or data found.
    
    Usage examples:
    - get_all_members_monthly_plan(selected_date="2026-02-01", include_unagreed=False)
    - get_all_members_monthly_plan(selected_date="2026-02-15", include_unagreed=True)
    """
    return get_all_members_monthly_plan_internal(selected_date, include_unagreed)


@mcp.tool()
def get_members_below_weekly_threshold(
    selected_date: str,
    threshold: float = 40.0,
    include_unagreed: bool = True
) -> Optional[list]:
    """
    Find members who have less than the threshold hours planned for a specific week.
    
    Use this to identify team members who are under-planned for the week.
    Default threshold is 40 hours (standard full-time week).
    
    This is useful for answering questions like:
    - "다음주 40시간의 계획이 잡혀 있지 않은 사람" (people without 40h planned next week)
    - "Who has less than full planning for next week?"
    
    Parameters:
    - selected_date (str): Date in YYYY-MM-DD format to determine which week.
    - threshold (float): Minimum hours threshold. Default is 40.0 hours.
    - include_unagreed (bool):
        * True (default): Include both agreed and unagreed tasks
        * False: Only count agreed tasks
    
    Returns:
    - list[dict] | None: List of members below threshold, sorted by hours (lowest first):
      * 'name': Member name
      * 'hours': Total planned hours
      * 'pv': Total PV
      * 'shortfall': How many hours below threshold
      * 'agreed_hours': Hours from agreed tasks only
      * 'agreed_pv': PV from agreed tasks only
      Returns None if all members meet threshold or no data found.
    
    Usage examples:
    - get_members_below_weekly_threshold(selected_date="2026-01-27")
    - get_members_below_weekly_threshold(selected_date="2026-01-27", threshold=40.0, include_unagreed=True)
    """
    all_plans = get_all_members_weekly_plan_internal(selected_date, include_unagreed)
    
    if not all_plans:
        return None
    
    below_threshold = []
    
    for member in all_plans:
        if member['total_hours'] < threshold:
            below_threshold.append({
                'name': member['name'],
                'hours': member['total_hours'],
                'pv': member['total_pv'],
                'shortfall': threshold - member['total_hours'],
                'agreed_hours': member['agreed_hours'],
                'agreed_pv': member['agreed_pv']
            })
    
    # Sort by hours (lowest first)
    below_threshold.sort(key=lambda x: x['hours'])
    
    return below_threshold if below_threshold else None


@mcp.tool()
def get_members_below_monthly_threshold(
    selected_date: str,
    threshold: float = 160.0,
    include_unagreed: bool = True
) -> Optional[list]:
    """
    Find members who have less than the threshold hours planned for a specific month.
    
    Use this to identify team members who are under-planned for the month.
    Default threshold is 160 hours (standard full-time month: 4 weeks × 40 hours).
    
    This is useful for answering questions like:
    - "다음달 160시간의 계획이 잡혀 있지 않은 사람" (people without 160h planned next month)
    - "Who has less than full planning for next month?"
    
    Parameters:
    - selected_date (str): Date in YYYY-MM-DD format to determine which month.
    - threshold (float): Minimum hours threshold. Default is 160.0 hours.
    - include_unagreed (bool):
        * True (default): Include both agreed and unagreed tasks
        * False: Only count agreed tasks
    
    Returns:
    - list[dict] | None: List of members below threshold, sorted by hours (lowest first):
      * 'name': Member name
      * 'hours': Total planned hours
      * 'pv': Total PV
      * 'shortfall': How many hours below threshold
      * 'agreed_hours': Hours from agreed tasks only
      * 'agreed_pv': PV from agreed tasks only
      Returns None if all members meet threshold or no data found.
    
    Usage examples:
    - get_members_below_monthly_threshold(selected_date="2026-02-01")
    - get_members_below_monthly_threshold(selected_date="2026-02-15", threshold=160.0, include_unagreed=True)
    """
    all_plans = get_all_members_monthly_plan_internal(selected_date, include_unagreed)
    
    if not all_plans:
        return None
    
    below_threshold = []
    
    for member in all_plans:
        if member['total_hours'] < threshold:
            below_threshold.append({
                'name': member['name'],
                'hours': member['total_hours'],
                'pv': member['total_pv'],
                'shortfall': threshold - member['total_hours'],
                'agreed_hours': member['agreed_hours'],
                'agreed_pv': member['agreed_pv']
            })
    
    # Sort by hours (lowest first)
    below_threshold.sort(key=lambda x: x['hours'])
    
    return below_threshold if below_threshold else None


# Achievement Analysis - All Members
@mcp.tool()
def get_all_members_weekly_achievement(
    selected_date: str,
    status: str = '완료됨'
) -> Optional[list]:
    """
    Get achievement hours, EV, PV, and CPI for ALL members for a specific week.
    
    Use this when user asks about "전체 인원의 달성" (all personnel's achievement) for a week.
    Tracks actual work completed/in-review based on status filter.
    
    CPI (Cost Performance Index) = EV / PV
    - CPI > 1.0: Over-performing (delivering more value than planned)
    - CPI = 1.0: On target
    - CPI < 1.0: Under-performing
    
    Parameters:
    - selected_date (str): Date in YYYY-MM-DD format to determine which week.
    - status (str): Status filter for achievement tracking. Options:
        * '완료됨' (default): Completed tasks (status_id=5)
        * '검수대기': Review waiting tasks (status_id=3)
        * '완료됨,검수대기': Both completed and review waiting
    
    Returns:
    - list[dict] | None: List of all members with their achievement data:
      * 'name': Member name
      * 'hours': Achieved hours
      * 'pv': Total PV for achieved tasks
      * 'ev': Total EV (Earned Value)
      * 'cpi': Cost Performance Index (EV/PV, or 0 if PV=0)
      Returns None if no users or data found.
    
    Usage examples:
    - get_all_members_weekly_achievement(selected_date="2026-01-20", status='완료됨')
    - get_all_members_weekly_achievement(selected_date="2026-01-13", status='검수대기')
    """
    return get_all_members_weekly_achievement_internal(selected_date, status, issue_statuses)


@mcp.tool()
def get_all_members_monthly_achievement(
    selected_date: str,
    status: str = '완료됨'
) -> Optional[list]:
    """
    Get achievement hours, EV, PV, and CPI for ALL members for a specific month.
    
    Use this when user asks about "전체 인원의 달성" (all personnel's achievement) for a month.
    
    CPI (Cost Performance Index) = EV / PV
    - CPI > 1.0: Over-performing
    - CPI = 1.0: On target
    - CPI < 1.0: Under-performing
    
    Parameters:
    - selected_date (str): Date in YYYY-MM-DD format to determine which month.
    - status (str): Status filter for achievement tracking. Options:
        * '완료됨' (default): Completed tasks (status_id=5)
        * '검수대기': Review waiting tasks (status_id=3)
        * '완료됨,검수대기': Both completed and review waiting
    
    Returns:
    - list[dict] | None: List of all members with their achievement data:
      * 'name': Member name
      * 'hours': Achieved hours
      * 'pv': Total PV for achieved tasks
      * 'ev': Total EV (Earned Value)
      * 'cpi': Cost Performance Index (EV/PV, or 0 if PV=0)
      Returns None if no users or data found.
    
    Usage examples:
    - get_all_members_monthly_achievement(selected_date="2026-01-15", status='완료됨')
    - get_all_members_monthly_achievement(selected_date="2025-12-15", status='검수대기')
    """
    return get_all_members_monthly_achievement_internal(selected_date, status, issue_statuses)


@mcp.tool()
def get_members_below_weekly_achievement_threshold(
    selected_date: str,
    threshold: float = 40.0,
    status: str = '완료됨'
) -> Optional[list]:
    """
    Find members who achieved less than threshold hours for a specific week.
    
    Use this to identify team members who under-achieved for the week.
    Default threshold is 40 hours (standard full-time week).
    
    This is useful for answering questions like:
    - "이번주 40시간을 달성하지 못한 사람" (people who didn't achieve 40h this week)
    - "Who completed less than 40 hours this week?"
    
    Parameters:
    - selected_date (str): Date in YYYY-MM-DD format to determine which week.
    - threshold (float): Minimum hours threshold. Default is 40.0 hours.
    - status (str): Status filter. Options:
        * '완료됨' (default): Completed tasks only
        * '검수대기': Review waiting tasks only
        * '완료됨,검수대기': Both
    
    Returns:
    - list[dict] | None: List of members below threshold, sorted by hours (lowest first):
      * 'name': Member name
      * 'hours': Achieved hours
      * 'ev': Total EV
      * 'pv': Total PV
      * 'cpi': Cost Performance Index
      * 'shortfall': How many hours below threshold
      Returns None if all members meet threshold or no data found.
    
    Usage examples:
    - get_members_below_weekly_achievement_threshold(selected_date="2026-01-20")
    - get_members_below_weekly_achievement_threshold(selected_date="2026-01-20", status='검수대기')
    """
    all_achievements = get_all_members_weekly_achievement_internal(selected_date, status, issue_statuses)
    
    if not all_achievements:
        return None
    
    below_threshold = []
    
    for member in all_achievements:
        if member['hours'] < threshold:
            below_threshold.append({
                'name': member['name'],
                'hours': member['hours'],
                'ev': member['ev'],
                'pv': member['pv'],
                'cpi': member['cpi'],
                'shortfall': threshold - member['hours']
            })
    
    # Sort by hours (lowest first)
    below_threshold.sort(key=lambda x: x['hours'])
    
    return below_threshold if below_threshold else None


@mcp.tool()
def get_members_below_monthly_achievement_threshold(
    selected_date: str,
    threshold: float = 160.0,
    status: str = '완료됨'
) -> Optional[list]:
    """
    Find members who achieved less than threshold hours for a specific month.
    
    Use this to identify team members who under-achieved for the month.
    Default threshold is 160 hours (standard full-time month: 4 weeks × 40 hours).
    
    This is useful for answering questions like:
    - "이번달 160시간을 달성하지 못한 사람" (people who didn't achieve 160h this month)
    - "Who completed less than 160 hours this month?"
    
    Parameters:
    - selected_date (str): Date in YYYY-MM-DD format to determine which month.
    - threshold (float): Minimum hours threshold. Default is 160.0 hours.
    - status (str): Status filter. Options:
        * '완료됨' (default): Completed tasks only
        * '검수대기': Review waiting tasks only
        * '완료됨,검수대기': Both
    
    Returns:
    - list[dict] | None: List of members below threshold, sorted by hours (lowest first):
      * 'name': Member name
      * 'hours': Achieved hours
      * 'ev': Total EV
      * 'pv': Total PV
      * 'cpi': Cost Performance Index
      * 'shortfall': How many hours below threshold
      Returns None if all members meet threshold or no data found.
    
    Usage examples:
    - get_members_below_monthly_achievement_threshold(selected_date="2026-01-15")
    - get_members_below_monthly_achievement_threshold(selected_date="2025-12-15", status='검수대기')
    """
    all_achievements = get_all_members_monthly_achievement_internal(selected_date, status, issue_statuses)
    
    if not all_achievements:
        return None
    
    below_threshold = []
    
    for member in all_achievements:
        if member['hours'] < threshold:
            below_threshold.append({
                'name': member['name'],
                'hours': member['hours'],
                'ev': member['ev'],
                'pv': member['pv'],
                'cpi': member['cpi'],
                'shortfall': threshold - member['hours']
            })
    
    # Sort by hours (lowest first)
    below_threshold.sort(key=lambda x: x['hours'])
    
    return below_threshold if below_threshold else None


@mcp.tool()
def get_all_members_ytd_achievement(
    current_date: str,
    status: str = '완료됨'
) -> Optional[list]:
    """
    Get year-to-date (YTD) cumulative achievement for ALL members up to a specific date.
    
    Use this when user asks about "지금까지 누적" (cumulative so far) or 
    "올해 누적" (this year's cumulative) achievement.
    
    This calculates the cumulative hours, PV, EV, and CPI from the beginning 
    of the year up to the specified date.
    
    Parameters:
    - current_date (str): Date in YYYY-MM-DD format up to which to calculate YTD.
    - status (str): Status filter. Options:
        * '완료됨' (default): Completed tasks only
        * '검수대기': Review waiting tasks only
        * '완료됨,검수대기': Both
    
    Returns:
    - list[dict] | None: List of all members with their YTD achievement:
      * 'name': Member name
      * 'ytd_hours': Year-to-date hours
      * 'ytd_pv': Year-to-date PV
      * 'ytd_ev': Year-to-date EV
      * 'ytd_cpi': Year-to-date CPI (EV/PV)
      * 'target_hours': Expected target hours based on weeks elapsed
      * 'hours_vs_target': Difference from target (negative = under-target)
      Returns None if no users or data found.
    
    Usage examples:
    - get_all_members_ytd_achievement(current_date="2026-01-19", status='완료됨')
    """
    return get_all_members_ytd_achievement_internal(current_date, status, issue_statuses)


@mcp.tool()
def get_members_below_ytd_target(
    current_date: str,
    status: str = '완료됨'
) -> Optional[list]:
    """
    Find members who haven't met their year-to-date cumulative hour target.
    
    Use this when user asks:
    - "지금까지 누적해서 목표시간을 달성하지 못한 사람" 
      (people who haven't achieved cumulative target hours)
    
    Target is calculated as: (weeks elapsed in year) × 40 hours/week
    
    Parameters:
    - current_date (str): Date in YYYY-MM-DD format for YTD calculation.
    - status (str): Status filter. Options:
        * '완료됨' (default): Completed tasks only
        * '검수대기': Review waiting tasks only
        * '완료됨,검수대기': Both
    
    Returns:
    - list[dict] | None: List of members below YTD target, sorted by shortfall:
      * 'name': Member name
      * 'ytd_hours': Year-to-date hours achieved
      * 'target_hours': Expected target hours
      * 'shortfall': Hours below target (positive number)
      * 'ytd_ev': Year-to-date EV
      * 'ytd_pv': Year-to-date PV
      * 'ytd_cpi': Year-to-date CPI
      Returns None if all members meet target or no data found.
    
    Usage examples:
    - get_members_below_ytd_target(current_date="2026-01-19")
    """
    all_ytd = get_all_members_ytd_achievement_internal(current_date, status, issue_statuses)
    
    if not all_ytd:
        return None
    
    below_target = []
    
    for member in all_ytd:
        if member['hours_vs_target'] < 0:  # Below target
            below_target.append({
                'name': member['name'],
                'ytd_hours': member['ytd_hours'],
                'target_hours': member['target_hours'],
                'shortfall': abs(member['hours_vs_target']),
                'ytd_ev': member['ytd_ev'],
                'ytd_pv': member['ytd_pv'],
                'ytd_cpi': member['ytd_cpi']
            })
    
    # Sort by shortfall (largest shortfall first)
    below_target.sort(key=lambda x: x['shortfall'], reverse=True)
    
    return below_target if below_target else None


@mcp.tool()
def get_members_below_cpi_threshold(
    current_date: str,
    cpi_threshold: float = 1.0,
    status: str = '완료됨'
) -> Optional[list]:
    """
    Find members with year-to-date CPI below threshold (under-performing).
    
    Use this when user asks:
    - "지금까지 누적해서 CPI를 달성하지 못한 사람" 
      (people who haven't achieved CPI target)
    
    CPI (Cost Performance Index) = EV / PV
    - CPI < 1.0: Under-performing (delivering less value than planned)
    - CPI = 1.0: On target
    - CPI > 1.0: Over-performing
    
    Parameters:
    - current_date (str): Date in YYYY-MM-DD format for YTD calculation.
    - cpi_threshold (float): Minimum CPI threshold. Default is 1.0.
    - status (str): Status filter. Options:
        * '완료됨' (default): Completed tasks only
        * '검수대기': Review waiting tasks only
        * '완료됨,검수대기': Both
    
    Returns:
    - list[dict] | None: List of members below CPI threshold, sorted by CPI (lowest first):
      * 'name': Member name
      * 'ytd_hours': Year-to-date hours
      * 'ytd_ev': Year-to-date EV
      * 'ytd_pv': Year-to-date PV
      * 'ytd_cpi': Year-to-date CPI
      * 'cpi_gap': How far below threshold (positive number)
      Returns None if all members meet CPI threshold or no data found.
    
    Usage examples:
    - get_members_below_cpi_threshold(current_date="2026-01-19")
    - get_members_below_cpi_threshold(current_date="2026-01-19", cpi_threshold=0.9)
    """
    all_ytd = get_all_members_ytd_achievement_internal(current_date, status, issue_statuses)
    
    if not all_ytd:
        return None
    
    below_cpi = []
    
    for member in all_ytd:
        if member['ytd_cpi'] < cpi_threshold and member['ytd_pv'] > 0:
            below_cpi.append({
                'name': member['name'],
                'ytd_hours': member['ytd_hours'],
                'ytd_ev': member['ytd_ev'],
                'ytd_pv': member['ytd_pv'],
                'ytd_cpi': member['ytd_cpi'],
                'cpi_gap': cpi_threshold - member['ytd_cpi']
            })
    
    # Sort by CPI (lowest first)
    below_cpi.sort(key=lambda x: x['ytd_cpi'])
    
    return below_cpi if below_cpi else None


# Compliance Checking - Rules Validation
@mcp.tool()
def find_agreement_violations_removed(
    start_date: str,
    end_date: Optional[str] = None,
    assigned_to: Optional[str] = None
) -> Optional[list]:
    """
    Find issues where performance agreement (합의필요사항) was arbitrarily removed.
    
    This detects when someone cleared the '합의필요사항' field after it had content,
    which may indicate improper process bypass.
    
    Excludes changes made by 박지환(Rex) (user_id=5) as these are authorized.
    
    Use this when user asks:
    - "성과합의를 임의로 해제한 일감이 있는지" (issues with agreement arbitrarily removed)
    - "steven task에서 성과합의를 해제한 일감" (Steven's tasks with agreement removed)
    
    Parameters:
    - start_date (str): Start date in YYYY-MM-DD format to check from.
    - end_date (str, optional): End date in YYYY-MM-DD format. If None, checks up to today.
    - assigned_to (str, optional): Filter by assigned user name (e.g., "Steven"). 
                                   If None, checks all users' tasks.
    
    Returns:
    - list[dict] | None: List of issues with agreement violations:
      * 'issue_id': Issue ID
      * 'subject': Issue subject
      * 'assigned_to': Who the task is assigned to
      * 'removed_by': User name who removed the agreement
      * 'removed_by_id': User ID
      * 'removed_on': Date when removed
      * 'old_value': Previous agreement content
      Returns None if no violations found.
    
    Usage examples:
    - find_agreement_violations_removed(start_date="2026-01-01")
    - find_agreement_violations_removed(start_date="2026-01-19", end_date="2026-01-21")
    - find_agreement_violations_removed(start_date="2026-01-19", end_date="2026-01-21", assigned_to="Steven")
    """
    start_obj = parse_date(start_date)
    end_obj = parse_date(end_date) if end_date else datetime.date.today()
    
    # Fetch all issues updated in the date range
    params = {
        'updated_on': f'>={start_date}'
    }
    if end_date:
        params['updated_on'] = f'><{start_date}|{end_date}'
    
    # Filter by assigned user if specified
    if assigned_to:
        member_id = get_member_id(assigned_to, members)
        params['assigned_to_id'] = member_id
    
    issues = fetch_all_issues(params)
    
    if not issues:
        return None
    
    violations = []
    AUTHORIZED_USER_ID = 5  # 박지환(Rex) - authorized to modify agreements
    
    for issue in issues:
        issue_id = issue.get("id")
        journals = get_issue_journals(issue_id)
        
        if not journals:
            continue
        
        for journal in journals:
            # Skip if changed by authorized user (Rex)
            user_info = journal.get("user", {})
            if isinstance(user_info, dict) and user_info.get("id") == AUTHORIZED_USER_ID:
                continue
            
            journal_date = journal.get("created_on", "")
            if not journal_date:
                continue
            
            # Parse journal date
            try:
                journal_obj = datetime.datetime.fromisoformat(journal_date.replace('Z', '+00:00')).date()
                if not (start_obj <= journal_obj <= end_obj):
                    continue
            except:
                continue
            
            # Check if 합의필요사항 (cf_17) was changed from something to empty
            for change in journal.get("changes", []):
                if change.get("property") == "cf" and change.get("name") == "17":  # cf_17 = 합의필요사항
                    old_val = change.get("old_value")
                    new_val = change.get("new_value")
                    
                    # Violation: had content, now empty
                    if old_val and not new_val:
                        user_name = user_info.get("name", "Unknown") if isinstance(user_info, dict) else str(user_info)
                        user_id = user_info.get("id", None) if isinstance(user_info, dict) else None
                        
                        # Get assigned_to info
                        assigned_user = issue.get("assigned_to", {})
                        assigned_name = assigned_user.get("name", "Unassigned") if isinstance(assigned_user, dict) else "Unassigned"
                        
                        violations.append({
                            'issue_id': issue_id,
                            'subject': issue.get("subject"),
                            'assigned_to': assigned_name,
                            'removed_by': user_name,
                            'removed_by_id': user_id,
                            'removed_on': journal_date,
                            'old_value': old_val
                        })
    
    return violations if violations else None


@mcp.tool()
def find_hours_increased_after_agreement(
    start_date: str,
    end_date: Optional[str] = None,
    assigned_to: Optional[str] = None
) -> Optional[list]:
    """
    Find issues where estimated hours increased AFTER performance agreement was completed.
    
    This detects when someone increased hours after clearing '합의필요사항',
    which may violate the agreement process.
    
    Use this when user asks:
    - "성과합의 이후에 시간이 늘어난 일감이 있는지" (issues with hours increased after agreement)
    - "steven task에서 성과합의 이후 시간이 늘어난 일감" (Steven's tasks with hours increased after agreement)
    
    Parameters:
    - start_date (str): Start date in YYYY-MM-DD format to check from.
    - end_date (str, optional): End date in YYYY-MM-DD format. If None, checks up to today.
    - assigned_to (str, optional): Filter by assigned user name (e.g., "Steven").
                                   If None, checks all users' tasks.
    
    Returns:
    - list[dict] | None: List of issues with hour increase violations:
      * 'issue_id': Issue ID
      * 'subject': Issue subject
      * 'assigned_to': Who the task is assigned to
      * 'increased_by': User who increased hours
      * 'increased_on': Date when increased
      * 'old_hours': Previous hours
      * 'new_hours': New hours
      * 'increase': Amount of increase
      Returns None if no violations found.
    
    Usage examples:
    - find_hours_increased_after_agreement(start_date="2026-01-01")
    - find_hours_increased_after_agreement(start_date="2026-01-19", end_date="2026-01-21", assigned_to="Steven")
    """
    start_obj = parse_date(start_date)
    end_obj = parse_date(end_date) if end_date else datetime.date.today()
    
    params = {
        'updated_on': f'>={start_date}'
    }
    if end_date:
        params['updated_on'] = f'><{start_date}|{end_date}'
    
    # Filter by assigned user if specified
    if assigned_to:
        member_id = get_member_id(assigned_to, members)
        params['assigned_to_id'] = member_id
    
    issues = fetch_all_issues(params)
    
    violations = []
    
    for issue in issues:
        issue_id = issue.get("id")
        journals = get_issue_journals(issue_id)
        
        # Track when agreement was cleared
        agreement_cleared_date = None
        
        for journal in journals:
            journal_date = journal.get("created_on", "")
            if not journal_date:
                continue
            
            try:
                journal_obj = datetime.datetime.fromisoformat(journal_date.replace('Z', '+00:00'))
            except:
                continue
            
            for change in journal.get("changes", []):
                # Track when 합의필요사항 was cleared
                if change.get("property") == "cf" and change.get("name") == "17":
                    old_val = change.get("old_value")
                    new_val = change.get("new_value")
                    if old_val and not new_val:
                        agreement_cleared_date = journal_obj
                
                # Check if hours increased AFTER agreement was cleared
                if change.get("property") == "attr" and change.get("name") == "estimated_hours":
                    old_hours = float(change.get("old_value") or 0)
                    new_hours = float(change.get("new_value") or 0)
                    
                    if new_hours > old_hours and agreement_cleared_date and journal_obj > agreement_cleared_date:
                        if start_obj <= journal_obj.date() <= end_obj:
                            # Get assigned_to info
                            assigned_user = issue.get("assigned_to", {})
                            assigned_name = assigned_user.get("name", "Unassigned") if isinstance(assigned_user, dict) else "Unassigned"
                            
                            # Get user info from journal
                            user_info = journal.get("user", {})
                            user_name = user_info.get("name", "Unknown") if isinstance(user_info, dict) else str(user_info)
                            
                            violations.append({
                                'issue_id': issue_id,
                                'subject': issue.get("subject"),
                                'assigned_to': assigned_name,
                                'increased_by': user_name,
                                'increased_on': journal_date,
                                'old_hours': old_hours,
                                'new_hours': new_hours,
                                'increase': new_hours - old_hours
                            })
    
    return violations if violations else None


@mcp.tool()
def find_quality_review_removed(
    start_date: str,
    end_date: Optional[str] = None,
    assigned_to: Optional[str] = None
) -> Optional[list]:
    """
    Find issues where quality review requirement (품질검토필요) was arbitrarily removed.
    
    This detects when someone changed '초기계획WBS' from '품질검토필요' (value=1) to another value,
    which may indicate improper process bypass.
    
    Use this when user asks:
    - "품질검토필요 값이 임의로 해제된 일감이 있는지" (issues with quality review arbitrarily removed)
    - "steven task에서 품질검토필요를 해제한 일감" (Steven's tasks with quality review removed)
    
    Parameters:
    - start_date (str): Start date in YYYY-MM-DD format to check from.
    - end_date (str, optional): End date in YYYY-MM-DD format. If None, checks up to today.
    - assigned_to (str, optional): Filter by assigned user name (e.g., "Steven").
                                   If None, checks all users' tasks.
    
    Returns:
    - list[dict] | None: List of issues with quality review violations:
      * 'issue_id': Issue ID
      * 'subject': Issue subject
      * 'assigned_to': Who the task is assigned to
      * 'removed_by': User who removed quality review
      * 'removed_on': Date when removed
      * 'old_value': Previous value (품질검토필요=1)
      * 'new_value': New value
      Returns None if no violations found.
    
    Usage examples:
    - find_quality_review_removed(start_date="2026-01-01")
    - find_quality_review_removed(start_date="2026-01-19", end_date="2026-01-21", assigned_to="Steven")
    """
    start_obj = parse_date(start_date)
    end_obj = parse_date(end_date) if end_date else datetime.date.today()
    
    params = {
        'updated_on': f'>={start_date}'
    }
    if end_date:
        params['updated_on'] = f'><{start_date}|{end_date}'
    
    # Filter by assigned user if specified
    if assigned_to:
        member_id = get_member_id(assigned_to, members)
        params['assigned_to_id'] = member_id
    
    issues = fetch_all_issues(params)
    
    violations = []
    
    for issue in issues:
        issue_id = issue.get("id")
        journals = get_issue_journals(issue_id)
        
        for journal in journals:
            journal_date = journal.get("created_on", "")
            if not journal_date:
                continue
            
            try:
                journal_obj = datetime.datetime.fromisoformat(journal_date.replace('Z', '+00:00')).date()
                if not (start_obj <= journal_obj <= end_obj):
                    continue
            except:
                continue
            
            # Check if 초기계획WBS (cf_49) was changed from 품질검토필요 or 성과검토필요
            for change in journal.get("changes", []):
                if change.get("property") == "cf" and change.get("name") == "49":  # cf_49 = 초기계획WBS
                    old_val = change.get("old_value")
                    new_val = change.get("new_value")
                    
                    # Violation: was 품질검토필요 or 성과검토필요, now removed/changed
                    if old_val in ["품질검토필요", "성과검토필요"] and new_val not in ["품질검토필요", "성과검토필요"]:
                        # Get assigned_to info
                        assigned_user = issue.get("assigned_to", {})
                        assigned_name = assigned_user.get("name", "Unassigned") if isinstance(assigned_user, dict) else "Unassigned"
                        
                        # Get user info from journal
                        user_info = journal.get("user", {})
                        user_name = user_info.get("name", "Unknown") if isinstance(user_info, dict) else str(user_info)
                        
                        violations.append({
                            'issue_id': issue_id,
                            'subject': issue.get("subject"),
                            'assigned_to': assigned_name,
                            'removed_by': user_name,
                            'removed_on': journal_date,
                            'old_value': old_val,
                            'new_value': new_val
                        })
    
    return violations if violations else None


@mcp.tool()
def find_completed_mng_without_template(
    start_date: str,
    end_date: Optional[str] = None,
    assigned_to: Optional[str] = None
) -> Optional[list]:
    """
    Find completed management tasks (Mng tracker) that may not have applied standard template.
    
    This identifies completed Mng type tasks. Note: You may need to manually verify
    if the template was properly applied based on your organization's standards.
    
    Use this when user asks:
    - "완료된 관리 일감 중 관리 템플릿을 적용하지 않은 일감" 
      (completed management tasks without template)
    - "steven task에서 완료된 관리 일감" (Steven's completed management tasks)
    
    Parameters:
    - start_date (str): Start date in YYYY-MM-DD format to check from.
    - end_date (str, optional): End date in YYYY-MM-DD format. If None, checks up to today.
    - assigned_to (str, optional): Filter by assigned user name (e.g., "Steven").
                                   If None, checks all users' tasks.
    
    Returns:
    - list[dict] | None: List of completed Mng tasks:
      * 'issue_id': Issue ID
      * 'subject': Issue subject
      * 'assigned_to': Person assigned
      * 'completed_on': When it was completed
      * 'estimated_hours': Hours
      Note: Manual review needed to verify template application
      Returns None if no tasks found.
    
    Usage examples:
    - find_completed_mng_without_template(start_date="2026-01-01")
    - find_completed_mng_without_template(start_date="2026-01-19", end_date="2026-01-21", assigned_to="Steven")
    """
    start_obj = parse_date(start_date)
    end_obj = parse_date(end_date) if end_date else datetime.date.today()
    
    # Fetch completed Mng tasks
    params = {
        'status_id': '5',  # 완료됨
        'tracker_id': '10',  # Mng
        'updated_on': f'>={start_date}'
    }
    if end_date:
        params['updated_on'] = f'><{start_date}|{end_date}'
    
    # Filter by assigned user if specified
    if assigned_to:
        member_id = get_member_id(assigned_to, members)
        params['assigned_to_id'] = member_id
    
    issues = fetch_all_issues(params)
    
    results = []
    
    for issue in issues:
        issue_id = issue.get("id")
        journals = get_issue_journals(issue_id)
        
        # Find when it was completed
        completed_on = None
        for journal in journals:
            for change in journal.get("changes", []):
                if change.get("property") == "attr" and change.get("name") == "status_id":
                    if change.get("new_value") == "5":  # Changed to 완료됨
                        completed_on = journal.get("created_on")
                        break
        
        if completed_on:
            try:
                completed_obj = datetime.datetime.fromisoformat(completed_on.replace('Z', '+00:00')).date()
                if start_obj <= completed_obj <= end_obj:
                    results.append({
                        'issue_id': issue_id,
                        'subject': issue.get("subject"),
                        'assigned_to': issue.get("assigned_to", {}).get("name"),
                        'completed_on': completed_on,
                        'estimated_hours': issue.get("estimated_hours")
                    })
            except:
                pass
    
    return results if results else None


@mcp.tool()
def find_completed_tasks_without_attachments(
    start_date: str,
    end_date: Optional[str] = None,
    assigned_to: Optional[str] = None
) -> Optional[list]:
    """
    Find completed tasks that have no description or notes (deliverables/산출물).
    
    This identifies completed tasks that may be missing required deliverable documentation.
    Checks if the issue has a description field or any notes in journals.
    
    Use this when user asks:
    - "완료된 일감 중 산출물이 등록되지 않은 일감" 
      (completed tasks without deliverables registered)
    - "steven task에서 산출물이 없는 일감" (Steven's tasks without deliverables)
    
    Parameters:
    - start_date (str): Start date in YYYY-MM-DD format to check from.
    - end_date (str, optional): End date in YYYY-MM-DD format. If None, checks up to today.
    - assigned_to (str, optional): Filter by assigned user name (e.g., "Steven").
                                   If None, checks all users' tasks.
    
    Returns:
    - list[dict] | None: List of completed tasks without description or notes:
      * 'issue_id': Issue ID
      * 'subject': Issue subject
      * 'tracker': Task type
      * 'assigned_to': Person assigned
      * 'completed_on': When it was completed
      * 'estimated_hours': Hours
      Returns None if no tasks found.
    
    Usage examples:
    - find_completed_tasks_without_attachments(start_date="2026-01-01")
    - find_completed_tasks_without_attachments(start_date="2026-01-19", end_date="2026-01-21", assigned_to="Steven")
    """
    start_obj = parse_date(start_date)
    end_obj = parse_date(end_date) if end_date else datetime.date.today()
    
    # Fetch completed tasks
    params = {
        'status_id': '5',  # 완료됨
        'updated_on': f'>={start_date}'
    }
    if end_date:
        params['updated_on'] = f'><{start_date}|{end_date}'
    
    # Filter by assigned user if specified
    if assigned_to:
        member_id = get_member_id(assigned_to, members)
        params['assigned_to_id'] = member_id
    
    issues = fetch_all_issues(params)
    
    results = []
    
    for issue in issues:
        issue_id = issue.get("id")
        
        # Get full issue details to check description
        full_issue = get_issue_details(issue_id)
        if not full_issue:
            continue
        
        # Check if has description or notes
        has_description = bool(full_issue.get("description", "").strip())
        
        # Check if has notes in journals
        has_notes = False
        journals = full_issue.get("journals", [])
        for journal in journals:
            if journal.get("notes", "").strip():
                has_notes = True
                break
        
        # If no description and no notes, it's missing documentation
        if not has_description and not has_notes:
            # Find when it was completed
            completed_on = None
            for journal in journals:
                for change in journal.get("changes", []):
                    if change.get("property") == "attr" and change.get("name") == "status_id":
                        if change.get("new_value") == "5":  # Changed to 완료됨
                            completed_on = journal.get("created_on")
                            break
            
            if completed_on:
                try:
                    completed_obj = datetime.datetime.fromisoformat(completed_on.replace('Z', '+00:00')).date()
                    if start_obj <= completed_obj <= end_obj:
                        results.append({
                            'issue_id': issue_id,
                            'subject': issue.get("subject"),
                            'tracker': issue.get("tracker", {}).get("name"),
                            'assigned_to': issue.get("assigned_to", {}).get("name"),
                            'completed_on': completed_on,
                            'estimated_hours': issue.get("estimated_hours")
                        })
                except:
                    pass
    
    return results if results else None


@mcp.tool()
def find_sprint_transfers_after_underachievement(
    last_week_date: str,
    threshold: float = 40.0
) -> Optional[list]:
    """
    Find people who transferred last week's tasks to an earlier week after not achieving 40h.
    
    This detects when someone moved tasks backward in time (changed 스프린트(주) to an earlier week)
    after failing to complete 40 hours in the original sprint week.
    
    Use this when user asks:
    - "지난 주 일감이 40시간 달성이 안된 상태에서, 이전 주로 이관된 사람의 스프린트" 
      (people who transferred to previous week after not achieving 40h last week)
    
    Parameters:
    - last_week_date (str): Date in YYYY-MM-DD format within last week to check.
    - threshold (float): Hour achievement threshold. Default is 40.0 hours.
    
    Returns:
    - list[dict] | None: List of people with sprint transfer violations:
      * 'name': Member name
      * 'last_week_hours': Hours achieved last week (below threshold)
      * 'transferred_issues': List of issues transferred backward:
        - 'issue_id': Issue ID
        - 'subject': Issue subject
        - 'transferred_by': Who moved it
        - 'transferred_on': When it was moved
        - 'old_sprint_week': Original sprint week
        - 'new_sprint_week': New (earlier) sprint week
      Returns None if no violations found.
    
    Usage examples:
    - find_sprint_transfers_after_underachievement(last_week_date="2026-01-13")
    """
    # First, get who didn't achieve threshold last week
    under_achievers = get_members_below_weekly_achievement_threshold_internal(
        selected_date=last_week_date,
        threshold=threshold,
        status='완료됨',
        issue_statuses=issue_statuses
    )
    
    if not under_achievers:
        return None
    
    date_obj = parse_date(last_week_date)
    week_label, month_label = get_week_and_month_label(date_obj)
    
    violations = []
    
    for member in under_achievers:
        name = member['name']
        member_id = member['member_id']
        
        # Fetch issues assigned to this member in that year
        params = {
            'assigned_to_id': member_id,
            'cf_38': str(date_obj.year),
            'updated_on': f'>={last_week_date}'
        }
        
        issues = fetch_all_issues(params)
        
        transferred_issues = []
        
        for issue in issues:
            issue_id = issue.get("id")
            journals = get_issue_journals(issue_id)
            
            for journal in journals:
                # Check if 스프린트(주) (cf_41) was changed
                for change in journal.get("changes", []):
                    if change.get("property") == "cf" and change.get("name") == "41":  # cf_41 = 스프린트(주)
                        old_week = change.get("old_value")
                        new_week = change.get("new_value")
                        
                        # Check if moved to an earlier week (backward transfer)
                        # Week format is like "1주차", "2주차", etc.
                        if old_week and new_week:
                            try:
                                old_week_num = int(old_week.replace("주차", ""))
                                new_week_num = int(new_week.replace("주차", ""))
                                
                                if new_week_num < old_week_num:  # Moved backward
                                    # Get user info from journal
                                    user_info = journal.get("user", {})
                                    user_name = user_info.get("name", "Unknown") if isinstance(user_info, dict) else str(user_info)
                                    
                                    transferred_issues.append({
                                        'issue_id': issue_id,
                                        'subject': issue.get("subject"),
                                        'transferred_by': user_name,
                                        'transferred_on': journal.get("created_on"),
                                        'old_sprint_week': old_week,
                                        'new_sprint_week': new_week
                                    })
                            except:
                                pass
        
        if transferred_issues:
            violations.append({
                'name': name,
                'last_week_hours': member['hours'],
                'transferred_issues': transferred_issues
            })
    
    return violations if violations else None


def main():
    """Main entry point for the mcp-socramine package."""
    mcp.run()

if __name__ == "__main__":
    main()