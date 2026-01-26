import os
import json
import datetime
from typing import Optional
from urllib.parse import urljoin
import httpx
import re


def request(path: str, method: str = 'get', data: Optional[dict] = None, params: Optional[dict] = None,
            content_type: str = 'application/json', content: Optional[bytes] = None, timeout: float = 120.0) -> dict:
    if data is None:
        data = {}
    if params is None:
        params = {}
    if content is None:
        content = b''
    headers = {'X-Redmine-API-Key': os.environ.get('REDMINE_API_KEY', ''), 'Content-Type': content_type}
    
    url = urljoin(os.environ.get('REDMINE_URL', ''), path)
    try:
        response = httpx.request(method=method.lower(), url=url, json=data, params=params, headers=headers,
                                 content=content, timeout=timeout)
        response.raise_for_status()
        body = None
        if response.content:
            try:
                body = response.json()
            except ValueError:
                body = response.content
        return {"status_code": response.status_code, "body": body, "error": ""}
    except Exception as e:
        status_code = 0
        body = None
        error_msg = f"{e.__class__.__name__}: {e}"
        if hasattr(e, 'response') and getattr(e, 'response') is not None:
            resp = getattr(e, 'response')
            try:
                status_code = resp.status_code
            except Exception:
                status_code = 0
            try:
                body = resp.json()
            except Exception:
                try:
                    body = resp.text
                except Exception:
                    body = None
        return {"status_code": status_code, "body": body, "error": error_msg}


def get_week_and_month_label(date_obj: datetime.date) -> tuple[str, str]:
    """
    Given a date, return the (week_label, month_label) according to the custom week/month logic.
    """
    first_day_of_month = date_obj.replace(day=1)
    days_until_first_wed = (2 - first_day_of_month.weekday() + 7) % 7  # 2 is Wednesday
    first_wed = first_day_of_month + datetime.timedelta(days=days_until_first_wed)
    monday_of_first_week = first_wed - datetime.timedelta(days=(first_wed.weekday() - 0))
    if date_obj < monday_of_first_week:
        last_day_of_prev_month = first_day_of_month - datetime.timedelta(days=1)
        first_day_of_prev_month = last_day_of_prev_month.replace(day=1)
        days_until_first_wed_prev = (2 - first_day_of_prev_month.weekday() + 7) % 7
        first_wed_prev = first_day_of_prev_month + datetime.timedelta(days=days_until_first_wed_prev)
        last_wed_prev = last_day_of_prev_month - datetime.timedelta(days=(last_day_of_prev_month.weekday() - 2) % 7)
        weeks_in_prev_month = ((last_wed_prev - first_wed_prev).days // 7) + 1
        if weeks_in_prev_month >= 5:
            week_label = "5주차"
            month_label = first_day_of_prev_month.strftime("%m월")
            return week_label, month_label
    last_day_of_month = (first_day_of_month + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
    last_wed_of_month = last_day_of_month - datetime.timedelta(days=(last_day_of_month.weekday() - 2) % 7)
    monday_of_last_week = last_wed_of_month - datetime.timedelta(days=(last_wed_of_month.weekday() - 0))
    weeks_in_month = ((last_wed_of_month - first_wed).days // 7) + 1
    if date_obj >= monday_of_last_week and weeks_in_month >= 5:
        week_label = "5주차"
        month_label = first_day_of_month.strftime("%m월")
        return week_label, month_label
    # Check if date is in the first week of the next month
    next_month = (first_day_of_month + datetime.timedelta(days=32)).replace(day=1)
    days_until_first_wed_next = (2 - next_month.weekday() + 7) % 7
    first_wed_next = next_month + datetime.timedelta(days=days_until_first_wed_next)
    monday_of_first_week_next = first_wed_next - datetime.timedelta(days=(first_wed_next.weekday() - 0))
    if monday_of_first_week_next <= date_obj < monday_of_first_week_next + datetime.timedelta(days=7):
        week_label = "1주차"
        month_label = next_month.strftime("%m월")
        return week_label, month_label
    # Otherwise, calculate week number for current month
    week_number = ((date_obj - monday_of_first_week).days // 7) + 1
    week_label = f"{week_number}주차"
    month_label = first_day_of_month.strftime("%m월")
    return week_label, month_label


def fetch_all_issues(params: dict) -> list:
    """
    Fetch all issues from Redmine using pagination, given initial params.
    Returns a combined list of all issues.
    """
    total_issues = []
    offset = 0
    limit = 100
    while True:
        paged_params = params.copy()
        paged_params.update({
            'limit': limit,
            'offset': offset
        })
        result = request('/issues.json', params=paged_params)
        if result["status_code"] == 200 and result["body"] and "issues" in result["body"]:
            issues = result["body"]["issues"]
            total_issues.extend(issues)
            if len(issues) < limit:
                break
            offset += limit
        else:
            raise RuntimeError(f"Failed to fetch issues: {result['error']}")
    return total_issues


def fetch_all_users(params: dict = {}) -> list:
    """
    Fetch all users from Redmine using pagination, given initial params (optional).
    Returns a combined list of all users with added 'name' field.
    """
    total_users = []
    offset = 0
    limit = 100
    while True:
        paged_params = params.copy()
        paged_params.update({
            'limit': limit,
            'offset': offset
        })
        result = request('/users.json', params=paged_params)
        if result["status_code"] == 200 and result["body"] and "users" in result["body"]:
            users = result["body"]["users"]
            # Add 'name' field to each user for convenience
            for user in users:
                firstname = user.get('firstname', '')
                lastname = user.get('lastname', '')
                
                if lastname and firstname:
                    # Check if lastname contains Korean characters (Hangul)
                    is_korean = bool(re.search(r'[가-힣]', lastname))
                    if is_korean:
                        # Korean names: lastname+firstname (no space)
                        user['name'] = f"{lastname}{firstname}"
                    else:
                        # English/Latin names: lastname firstname (with space)
                        user['name'] = f"{lastname} {firstname}"
                else:
                    user['name'] = user.get('login', str(user.get('id', '')))
            total_users.extend(users)
            if len(users) < limit:
                break
            offset += limit
        else:
            raise RuntimeError(f"Failed to fetch users: {result['error']}")
    return total_users


def get_member_id(name: str, members=None) -> str:
    """
    Look up the member ID by name (case-insensitive). Raise ValueError if not found.
    """
    if members is None:
        raise ValueError("members dictionary must be provided")
    name_key = name.strip().lower()
    members_lower = {k.strip().lower(): v for k, v in members.items()}
    member_id = members_lower.get(name_key)
    if not member_id:
        raise ValueError(f"Member '{name}' not found")
    return member_id


def fetch_all_projects(params: dict = {}) -> list:
    """
    Fetch all projects from Redmine using pagination, given initial params (optional).
    Returns a combined list of all projects.
    """
    total_projects = []
    offset = 0
    limit = 100
    while True:
        paged_params = params.copy()
        paged_params.update({
            'limit': limit,
            'offset': offset
        })
        result = request('/projects.json', params=paged_params)
        if result["status_code"] == 200 and result["body"] and "projects" in result["body"]:
            projects = result["body"]["projects"]
            total_projects.extend(projects)
            if len(projects) < limit:
                break
            offset += limit
        else:
            raise RuntimeError(f"Failed to fetch projects: {result['error']}")
    return total_projects


def get_project_id(project: str) -> str:
    """
    Retrieve all projects from Redmine and return the ID of the project whose name or identifier exactly matches the given project string (case-insensitive).
    Raise ValueError if not found.
    """
    projects = fetch_all_projects()
    project_lower = project.strip().lower()
    for p in projects:
        name_lower = p.get("name", "").strip().lower()
        identifier_lower = p.get("identifier", "").strip().lower()
        if project_lower == name_lower or project_lower == identifier_lower:
            return str(p["id"])
    raise ValueError(f"Project '{project}' not found")


def parse_status_param(status: Optional[str], issue_statuses) -> str:
    """
    Convert a comma-separated status string to a comma-separated status_id string using issue_statuses (case-insensitive).
    If status is None, returns '*'.
    """
    if status is None:
        return '*'
    status_names = [s.strip().lower() for s in status.split(',')]
    issue_statuses_lower = {k.strip().lower(): v for k, v in issue_statuses.items()}
    status_ids = [str(issue_statuses_lower.get(s, s)) for s in status_names]
    return ','.join(status_ids)


def parse_priority_param(priority: Optional[str], priorities) -> str:
    """
    Convert a comma-separated priority string to a comma-separated priority_id string using priorities (case-insensitive).
    """
    if priority is None:
        return ''
    priority_names = [s.strip().lower() for s in priority.split(',')]
    priorities_lower = {k.strip().lower(): v for k, v in priorities.items()}
    priority_ids = [str(priorities_lower.get(s, s)) for s in priority_names]
    return ','.join(priority_ids)


def parse_tracker_type_param(tracker_type: Optional[str], tracker_types) -> str:
    """
    Convert a comma-separated tracker_type string to a comma-separated tracker_type_id string using tracker_types (case-insensitive).
    """
    if tracker_type is None:
        return ''
    tracker_type_names = [s.strip().lower() for s in tracker_type.split(',')]
    tracker_types_lower = {k.strip().lower(): v for k, v in tracker_types.items()}
    tracker_type_ids = [str(tracker_types_lower.get(s, s)) for s in tracker_type_names]
    return ','.join(tracker_type_ids)


def parse_date(date_str: str) -> datetime.date:
    """
    Parse a date string in YYYY-MM-DD format to a datetime.date object. Raise ValueError if invalid.
    """
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("selected_date must be in YYYY-MM-DD format")


def get_issue_details(issue_id: int) -> Optional[dict]:
    """
    Fetch full details for a single issue including journals (history).
    """
    result = request(f'/issues/{issue_id}.json', params={'include': 'journals,children,attachments,relations'})
    if result["status_code"] == 200 and result["body"]:
        return result["body"].get("issue")
    return None


def get_issue_journals(issue_id: int) -> list:
    """
    Fetch the change history (journals) for an issue.
    Returns list of journal entries with details, user, and changes.
    """
    issue = get_issue_details(issue_id)
    if not issue:
        return []
    
    journals = issue.get("journals", [])
    history = []
    
    for journal in journals:
        entry = {
            "id": journal.get("id"),
            "user": journal.get("user", {}),  # Keep full user object with id and name
            "created_on": journal.get("created_on"),
            "notes": journal.get("notes"),
            "changes": []
        }
        
        # Parse details (field changes)
        for detail in journal.get("details", []):
            change = {
                "property": detail.get("property"),  # "attr" for attributes, "cf" for custom fields
                "name": detail.get("name"),
                "old_value": detail.get("old_value"),
                "new_value": detail.get("new_value")
            }
            entry["changes"].append(change)
        
        if entry["changes"] or entry["notes"]:  # Only include if there are changes or notes
            history.append(entry)
    
    return history


def get_issue_children(issue_id: int) -> list:
    """
    Fetch child issues of a parent issue.
    """
    issue = get_issue_details(issue_id)
    if not issue:
        return []
    
    children = issue.get("children", [])
    child_ids = [child.get("id") for child in children if child.get("id")]
    
    return child_ids


def get_issue_parent(issue_id: int) -> Optional[dict]:
    """
    Fetch parent issue information if it exists.
    """
    issue = get_issue_details(issue_id)
    if not issue:
        return None
    
    parent = issue.get("parent")
    if parent:
        return {
            "id": parent.get("id"),
            "subject": parent.get("subject")
        }
    return None


def get_issue_attachments(issue_id: int) -> list:
    """
    Fetch attachments for an issue.
    """
    issue = get_issue_details(issue_id)
    if not issue:
        return []
    
    attachments = issue.get("attachments", [])
    result = []
    
    for att in attachments:
        result.append({
            "id": att.get("id"),
            "filename": att.get("filename"),
            "filesize": att.get("filesize"),
            "content_type": att.get("content_type"),
            "author": att.get("author", {}).get("name"),
            "created_on": att.get("created_on")
        })
    
    return result


def compact_issues(issues):
    """
    Return a compact list of issues with only the most relevant fields.
    Ensures proper encoding of Unicode characters including Korean text.
    """
    def get_custom_field(issue, field_name):
        for field in issue.get('custom_fields', []):
            if field.get('name') == field_name:
                value = field.get('value')
                if isinstance(value, list):
                    return ', '.join(str(v) for v in value if v)
                return value
        return None

    result = [
        {
            "id": issue.get("id"),
            "project": issue.get("project", {}).get("name"),
            "tracker": issue.get("tracker", {}).get("name"),
            "status": issue.get("status", {}).get("name"),
            "priority": issue.get("priority", {}).get("name"),
            "author": issue.get("author", {}).get("name"),
            "assigned_to": issue.get("assigned_to", {}).get("name"),
            "subject": issue.get("subject"),
            # "description": issue.get("description"),
            "start_date": issue.get("start_date"),
            "due_date": issue.get("due_date"),
            "estimated_hours": issue.get("estimated_hours"),
            "Mission Level": get_custom_field(issue, "Mission Level"),
            "목표 년도": get_custom_field(issue, "목표 년도"),
            "PV": get_custom_field(issue, "PV"),
            "EV": get_custom_field(issue, "EV"),
            "합의필요사항": get_custom_field(issue, "합의필요사항"),
            "agreed": not bool(get_custom_field(issue, "합의필요사항")),
            "초기계획WBS": get_custom_field(issue, "초기계획WBS"),
            "스프린트(주)": get_custom_field(issue, "스프린트(주)"),
            "스프린트(월)": get_custom_field(issue, "스프린트(월)"),
        }
        for issue in issues
    ]
    
    # Ensure Unicode characters are preserved
    return json.loads(json.dumps(result, ensure_ascii=False))


def get_all_members_weekly_plan_internal(
    selected_date: str,
    include_unagreed: bool = True
) -> Optional[list]:
    """Internal helper function for weekly planning across all members."""
    users = fetch_all_users({'status': 1})  # 1 = active users only
    if not users:
        return None
    
    date_obj = parse_date(selected_date)
    week_label, month_label = get_week_and_month_label(date_obj)
    
    results = []
    
    for user in users:
        name = user.get('name')
        member_id = user.get('id')
        
        if not name or not member_id:
            continue
        
        params = {
            'assigned_to_id': member_id,
            'cf_38': str(date_obj.year),
            'cf_41': week_label,
            'cf_42': month_label,
        }
        
        issues = fetch_all_issues(params)
        
        agreed_hours = 0.0
        agreed_pv = 0.0
        unagreed_hours = 0.0
        unagreed_pv = 0.0
        
        for issue in issues:
            # Get estimated hours
            hours = float(issue.get("estimated_hours", 0) or 0)
            
            # Get PV from custom fields
            pv = 0.0
            for cf in issue.get("custom_fields", []):
                if cf.get("name") == "PV":
                    try:
                        pv = float(cf.get("value", 0) or 0)
                    except ValueError:
                        pass
                    break
            
            # Check if agreed (합의필요사항 is empty)
            is_agreed = True
            for cf in issue.get("custom_fields", []):
                if cf.get("name") == "합의필요사항":
                    if cf.get("value"):
                        is_agreed = False
                    break
            
            if is_agreed:
                agreed_hours += hours
                agreed_pv += pv
            else:
                unagreed_hours += hours
                unagreed_pv += pv
        
        if include_unagreed:
            total_hours = agreed_hours + unagreed_hours
            total_pv = agreed_pv + unagreed_pv
        else:
            total_hours = agreed_hours
            total_pv = agreed_pv
        
        results.append({
            'name': name,
            'member_id': member_id,
            'total_hours': total_hours,
            'total_pv': total_pv,
            'agreed_hours': agreed_hours,
            'agreed_pv': agreed_pv,
            'unagreed_hours': unagreed_hours,
            'unagreed_pv': unagreed_pv
        })
    
    return results if results else None


def get_all_members_monthly_plan_internal(
    selected_date: str,
    include_unagreed: bool = True
) -> Optional[list]:
    """Internal helper function for monthly planning across all members."""
    users = fetch_all_users({'status': 1})  # 1 = active users only
    if not users:
        return None
    
    date_obj = parse_date(selected_date)
    week_label, month_label = get_week_and_month_label(date_obj)
    
    results = []
    
    for user in users:
        name = user.get('name')
        member_id = user.get('id')
        
        if not name or not member_id:
            continue
        
        params = {
            'assigned_to_id': member_id,
            'cf_38': str(date_obj.year),
            'cf_42': month_label,
        }
        
        issues = fetch_all_issues(params)
        
        agreed_hours = 0.0
        agreed_pv = 0.0
        unagreed_hours = 0.0
        unagreed_pv = 0.0
        
        for issue in issues:
            # Get estimated hours
            hours = float(issue.get("estimated_hours", 0) or 0)
            
            # Get PV from custom fields
            pv = 0.0
            for cf in issue.get("custom_fields", []):
                if cf.get("name") == "PV":
                    try:
                        pv = float(cf.get("value", 0) or 0)
                    except ValueError:
                        pass
                    break
            
            # Check if agreed (합의필요사항 is empty)
            is_agreed = True
            for cf in issue.get("custom_fields", []):
                if cf.get("name") == "합의필요사항":
                    if cf.get("value"):
                        is_agreed = False
                    break
            
            if is_agreed:
                agreed_hours += hours
                agreed_pv += pv
            else:
                unagreed_hours += hours
                unagreed_pv += pv
        
        if include_unagreed:
            total_hours = agreed_hours + unagreed_hours
            total_pv = agreed_pv + unagreed_pv
        else:
            total_hours = agreed_hours
            total_pv = agreed_pv
        
        results.append({
            'name': name,
            'total_hours': total_hours,
            'total_pv': total_pv,
            'agreed_hours': agreed_hours,
            'agreed_pv': agreed_pv,
            'unagreed_hours': unagreed_hours,
            'unagreed_pv': unagreed_pv
        })
    
    return results if results else None


def get_all_members_monthly_achievement_internal(
    selected_date: str,
    status: str,
    issue_statuses: dict
) -> Optional[list]:
    """Internal helper function for monthly achievement across all members."""
    users = fetch_all_users({'status': 1})  # 1 = active users only
    if not users:
        return None
    
    status_id = parse_status_param(status, issue_statuses)
    date_obj = parse_date(selected_date)
    week_label, month_label = get_week_and_month_label(date_obj)
    
    results = []
    
    for user in users:
        name = user.get('name')
        member_id = user.get('id')
        
        if not name or not member_id:
            continue
        
        params = {
            'assigned_to_id': member_id,
            'status_id': status_id,
            'cf_38': str(date_obj.year),
            'cf_42': month_label,
        }
        
        issues = fetch_all_issues(params)
        
        total_hours = 0.0
        total_pv = 0.0
        total_ev = 0.0
        
        for issue in issues:
            # Get estimated hours
            hours = float(issue.get("estimated_hours", 0) or 0)
            total_hours += hours
            
            # Get PV and EV from custom fields
            for cf in issue.get("custom_fields", []):
                if cf.get("name") == "PV":
                    try:
                        total_pv += float(cf.get("value", 0) or 0)
                    except ValueError:
                        pass
                elif cf.get("name") == "EV":
                    try:
                        total_ev += float(cf.get("value", 0) or 0)
                    except ValueError:
                        pass
        
        # Calculate CPI
        cpi = total_ev / total_pv if total_pv > 0 else 0.0
        
        results.append({
            'name': name,
            'hours': total_hours,
            'pv': total_pv,
            'ev': total_ev,
            'cpi': cpi
        })
    
    return results if results else None


def get_all_members_weekly_achievement_internal(
    selected_date: str,
    status: str,
    issue_statuses: dict
) -> Optional[list]:
    """Internal helper function for weekly achievement across all members."""
    users = fetch_all_users({'status': 1})  # 1 = active users only
    if not users:
        return None
    
    status_id = parse_status_param(status, issue_statuses)
    date_obj = parse_date(selected_date)
    week_label, month_label = get_week_and_month_label(date_obj)
    
    results = []
    
    for user in users:
        name = user.get('name')
        member_id = user.get('id')
        
        if not name or not member_id:
            continue
        
        params = {
            'assigned_to_id': member_id,
            'status_id': status_id,
            'cf_38': str(date_obj.year),
            'cf_41': week_label,
            'cf_42': month_label,
        }
        
        issues = fetch_all_issues(params)
        
        total_hours = 0.0
        total_pv = 0.0
        total_ev = 0.0
        
        for issue in issues:
            # Get estimated hours
            hours = float(issue.get("estimated_hours", 0) or 0)
            total_hours += hours
            
            # Get PV and EV from custom fields
            for cf in issue.get("custom_fields", []):
                if cf.get("name") == "PV":
                    try:
                        total_pv += float(cf.get("value", 0) or 0)
                    except ValueError:
                        pass
                elif cf.get("name") == "EV":
                    try:
                        total_ev += float(cf.get("value", 0) or 0)
                    except ValueError:
                        pass
        
        # Calculate CPI
        cpi = total_ev / total_pv if total_pv > 0 else 0.0
        
        results.append({
            'name': name,
            'member_id': member_id,
            'hours': total_hours,
            'pv': total_pv,
            'ev': total_ev,
            'cpi': cpi
        })
    
    return results if results else None

    users = fetch_all_users({'status': 1})  # 1 = active users only
    if not users:
        return None
    
    date_obj = parse_date(selected_date)
    week_label, month_label = get_week_and_month_label(date_obj)
    
    results = []
    
    for user in users:
        name = user.get('name')
        member_id = user.get('id')
        
        if not name or not member_id:
            continue
        
        params = {
            'assigned_to_id': member_id,
            'cf_38': str(date_obj.year),
            'cf_42': month_label,
        }
        
        issues = fetch_all_issues(params)
        
        agreed_hours = 0.0
        agreed_pv = 0.0
        unagreed_hours = 0.0
        unagreed_pv = 0.0
        
        for issue in issues:
            # Get estimated hours
            hours = float(issue.get("estimated_hours", 0) or 0)
            
            # Get PV from custom fields
            pv = 0.0
            for cf in issue.get("custom_fields", []):
                if cf.get("name") == "PV":
                    try:
                        pv = float(cf.get("value", 0) or 0)
                    except ValueError:
                        pass
                    break
            
            # Check if agreed (합의필요사항 is empty)
            is_agreed = True
            for cf in issue.get("custom_fields", []):
                if cf.get("name") == "합의필요사항":
                    if cf.get("value"):
                        is_agreed = False
                    break
            
            if is_agreed:
                agreed_hours += hours
                agreed_pv += pv
            else:
                unagreed_hours += hours
                unagreed_pv += pv
        
        if include_unagreed:
            total_hours = agreed_hours + unagreed_hours
            total_pv = agreed_pv + unagreed_pv
        else:
            total_hours = agreed_hours
            total_pv = agreed_pv
        
        results.append({
            'name': name,
            'total_hours': total_hours,
            'total_pv': total_pv,
            'agreed_hours': agreed_hours,
            'agreed_pv': agreed_pv,
            'unagreed_hours': unagreed_hours,
            'unagreed_pv': unagreed_pv
        })
    
    return results if results else None


def get_all_members_ytd_achievement_internal(
    current_date: str,
    status: str,
    issue_statuses: dict
) -> Optional[list]:
    """Internal helper function for YTD achievement across all members."""
    import datetime
    
    users = fetch_all_users({'status': 1})  # 1 = active users only
    if not users:
        return None
    
    status_id = parse_status_param(status, issue_statuses)
    date_obj = parse_date(current_date)
    year = date_obj.year
    
    # Calculate how many weeks have elapsed in the year
    # Assuming standard work year: 40 hours/week target
    year_start = datetime.date(year, 1, 1)
    days_elapsed = (date_obj - year_start).days + 1
    weeks_elapsed = days_elapsed / 7.0
    target_hours = weeks_elapsed * 40.0  # 40 hours per week target
    
    results = []
    
    for user in users:
        name = user.get('name')
        member_id = user.get('id')
        
        if not name or not member_id:
            continue
        
        # Fetch all issues for the year with the specified status
        params = {
            'assigned_to_id': member_id,
            'status_id': status_id,
            'cf_38': str(year),
        }
        
        issues = fetch_all_issues(params)
        
        ytd_hours = 0.0
        ytd_pv = 0.0
        ytd_ev = 0.0
        
        for issue in issues:
            # Get estimated hours
            hours = float(issue.get("estimated_hours", 0) or 0)
            ytd_hours += hours
            
            # Get PV and EV from custom fields
            for cf in issue.get("custom_fields", []):
                if cf.get("name") == "PV":
                    try:
                        ytd_pv += float(cf.get("value", 0) or 0)
                    except ValueError:
                        pass
                elif cf.get("name") == "EV":
                    try:
                        ytd_ev += float(cf.get("value", 0) or 0)
                    except ValueError:
                        pass
        
        # Calculate YTD CPI
        ytd_cpi = ytd_ev / ytd_pv if ytd_pv > 0 else 0.0
        
        results.append({
            'name': name,
            'ytd_hours': ytd_hours,
            'ytd_pv': ytd_pv,
            'ytd_ev': ytd_ev,
            'ytd_cpi': ytd_cpi,
            'target_hours': target_hours,
            'hours_vs_target': ytd_hours - target_hours
        })
    
    return results if results else None


def get_members_below_weekly_achievement_threshold_internal(
    selected_date: str,
    threshold: float,
    status: str,
    issue_statuses: dict
) -> Optional[list]:
    """Internal helper for finding members below weekly achievement threshold."""
    all_achievements = get_all_members_weekly_achievement_internal(selected_date, status, issue_statuses)
    
    if not all_achievements:
        return None
    
    below_threshold = []
    
    for member in all_achievements:
        if member['hours'] < threshold:
            below_threshold.append({
                'name': member['name'],
                'member_id': member['member_id'],
                'hours': member['hours'],
                'ev': member['ev'],
                'pv': member['pv'],
                'cpi': member['cpi'],
                'shortfall': threshold - member['hours']
            })
    
    # Sort by hours (lowest first)
    below_threshold.sort(key=lambda x: x['hours'])
    
    return below_threshold if below_threshold else None


def get_all_members_ytd_achievement_internal(
    current_date: str,
    status: str,
    issue_statuses: dict
) -> Optional[list]:
    """Internal helper function for YTD achievement across all members."""
    import datetime
    
    users = fetch_all_users({'status': 1})  # 1 = active users only
    if not users:
        return None
    
    status_id = parse_status_param(status, issue_statuses)
    date_obj = parse_date(current_date)
    year = date_obj.year
    
    # Calculate how many weeks have elapsed in the year
    # Assuming standard work year: 40 hours/week target
    year_start = datetime.date(year, 1, 1)
    days_elapsed = (date_obj - year_start).days + 1
    weeks_elapsed = days_elapsed / 7.0
    target_hours = weeks_elapsed * 40.0  # 40 hours per week target
    
    results = []
    
    for user in users:
        name = user.get('name')
        member_id = user.get('id')
        
        if not name or not member_id:
            continue
        
        # Fetch all issues for the year with the specified status
        params = {
            'assigned_to_id': member_id,
            'status_id': status_id,
            'cf_38': str(year),
        }
        
        issues = fetch_all_issues(params)
        
        ytd_hours = 0.0
        ytd_pv = 0.0
        ytd_ev = 0.0
        
        for issue in issues:
            # Get estimated hours
            hours = float(issue.get("estimated_hours", 0) or 0)
            ytd_hours += hours
            
            # Get PV and EV from custom fields
            for cf in issue.get("custom_fields", []):
                if cf.get("name") == "PV":
                    try:
                        ytd_pv += float(cf.get("value", 0) or 0)
                    except ValueError:
                        pass
                elif cf.get("name") == "EV":
                    try:
                        ytd_ev += float(cf.get("value", 0) or 0)
                    except ValueError:
                        pass
        
        # Calculate YTD CPI
        ytd_cpi = ytd_ev / ytd_pv if ytd_pv > 0 else 0.0
        
        results.append({
            'name': name,
            'member_id': member_id,
            'ytd_hours': ytd_hours,
            'ytd_pv': ytd_pv,
            'ytd_ev': ytd_ev,
            'ytd_cpi': ytd_cpi,
            'target_hours': target_hours,
            'hours_vs_target': ytd_hours - target_hours
        })
    
    return results if results else None


def get_members_below_weekly_achievement_threshold_internal(
    selected_date: str,
    threshold: float,
    status: str,
    issue_statuses: dict
) -> Optional[list]:
    """Internal helper for finding members below weekly achievement threshold."""
    all_achievements = get_all_members_weekly_achievement_internal(selected_date, status, issue_statuses)
    
    if not all_achievements:
        return None
    
    below_threshold = []
    
    for member in all_achievements:
        if member['hours'] < threshold:
            below_threshold.append({
                'name': member['name'],
                'member_id': member['member_id'],
                'hours': member['hours'],
                'ev': member['ev'],
                'pv': member['pv'],
                'cpi': member['cpi'],
                'shortfall': threshold - member['hours']
            })
    
    # Sort by hours (lowest first)
    below_threshold.sort(key=lambda x: x['hours'])
    
    return below_threshold if below_threshold else None
