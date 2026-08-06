from src.shared.errors import ForbiddenError
from src.workspaces.models.workspace_member import MemberRole


def check_role(min_role: MemberRole, actual_role: MemberRole | None):
    hierarchy = {MemberRole.admin: 3, MemberRole.editor: 2, MemberRole.viewer: 1}
    if actual_role is None:
        raise ForbiddenError("Access denied.")
    if hierarchy.get(actual_role, 0) < hierarchy.get(min_role, 0):
        raise ForbiddenError(f"Requires {min_role.value} role or higher.")
