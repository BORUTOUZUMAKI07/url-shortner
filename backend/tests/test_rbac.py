import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.models.user import User
from src.shared.middleware.rbac import require_role
from src.workspaces.models.workspace import Workspace
from src.workspaces.models.workspace_member import MemberRole, WorkspaceMember


@pytest.mark.asyncio
async def test_require_role_admin(db: AsyncSession, test_user: User, test_workspace: Workspace):
    member = WorkspaceMember(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        role=MemberRole.admin,
    )
    db.add(member)
    await db.flush()

    result = await require_role(workspace_id=test_workspace.id, user_id=test_user.id, min_role=MemberRole.admin, db=db)
    assert result is True


@pytest.mark.asyncio
async def test_require_role_editor_has_admin(db: AsyncSession, test_user: User, test_workspace: Workspace):
    member = WorkspaceMember(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        role=MemberRole.admin,
    )
    db.add(member)
    await db.flush()

    result = await require_role(workspace_id=test_workspace.id, user_id=test_user.id, min_role=MemberRole.editor, db=db)
    assert result is True


@pytest.mark.asyncio
async def test_require_role_viewer_denied_for_editor(db: AsyncSession, test_user: User, test_workspace: Workspace):
    member = WorkspaceMember(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        role=MemberRole.viewer,
    )
    db.add(member)
    await db.flush()

    with pytest.raises(HTTPException) as exc:
        await require_role(workspace_id=test_workspace.id, user_id=test_user.id, min_role=MemberRole.editor, db=db)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_no_membership(db: AsyncSession, test_workspace: Workspace):
    with pytest.raises(HTTPException) as exc:
        await require_role(workspace_id=test_workspace.id, user_id=99999, min_role=MemberRole.viewer, db=db)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_role_hierarchy_admin_greater_than_viewer(db: AsyncSession, test_user: User, test_workspace: Workspace):
    member = WorkspaceMember(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        role=MemberRole.admin,
    )
    db.add(member)
    await db.flush()

    result = await require_role(workspace_id=test_workspace.id, user_id=test_user.id, min_role=MemberRole.viewer, db=db)
    assert result is True
