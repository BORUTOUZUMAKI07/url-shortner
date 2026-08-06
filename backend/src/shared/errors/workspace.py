from src.shared.errors.common import BadRequestError, ConflictError, ForbiddenError, NotFoundError


class WorkspaceNotFound(NotFoundError):
    def __init__(self):
        super().__init__(detail="Workspace not found or access denied.")


class OnlyAdminCanInvite(ForbiddenError):
    def __init__(self):
        super().__init__(detail="Only admins can invite members.")


class CannotInviteOwner(ConflictError):
    def __init__(self):
        super().__init__(detail="Cannot invite the workspace owner.")


class AlreadyMember(ConflictError):
    def __init__(self):
        super().__init__(detail="User is already a member of this workspace.")


class PendingInviteExists(ConflictError):
    def __init__(self):
        super().__init__(detail="A pending invite already exists for this email.")


class InviteNotFound(NotFoundError):
    def __init__(self):
        super().__init__(detail="Invite not found.")


class InviteExpired(BadRequestError):
    def __init__(self):
        super().__init__(detail="Invite has expired.")


class InviteEmailMismatch(ForbiddenError):
    def __init__(self):
        super().__init__(detail="This invite was sent to a different email address.")


class CannotRemoveOwner(BadRequestError):
    def __init__(self):
        super().__init__(detail="Cannot remove the workspace owner.")


class OnlyOwnerCanChangeRoles(ForbiddenError):
    def __init__(self):
        super().__init__(detail="Only the workspace owner can change roles.")


class MemberNotFound(NotFoundError):
    def __init__(self):
        super().__init__(detail="Member not found.")


class RoleTooLow(ForbiddenError):
    def __init__(self, min_role: str):
        super().__init__(detail=f"Requires {min_role} role or higher.")
