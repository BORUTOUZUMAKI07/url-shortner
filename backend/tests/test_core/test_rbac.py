import pytest

from src.core.rbac import check_role
from src.errors import ForbiddenError
from src.models.workspace_member import MemberRole


class TestCheckRole:
    def test_admin_meets_admin(self):
        assert check_role(MemberRole.admin, MemberRole.admin) is None

    def test_admin_meets_editor(self):
        assert check_role(MemberRole.editor, MemberRole.admin) is None

    def test_admin_meets_viewer(self):
        assert check_role(MemberRole.viewer, MemberRole.admin) is None

    def test_editor_meets_editor(self):
        assert check_role(MemberRole.editor, MemberRole.editor) is None

    def test_editor_meets_viewer(self):
        assert check_role(MemberRole.viewer, MemberRole.editor) is None

    def test_viewer_meets_viewer(self):
        assert check_role(MemberRole.viewer, MemberRole.viewer) is None

    def test_viewer_denied_for_editor(self):
        with pytest.raises(ForbiddenError) as exc:
            check_role(MemberRole.editor, MemberRole.viewer)
        assert "editor" in str(exc.value.detail).lower()

    def test_editor_denied_for_admin(self):
        with pytest.raises(ForbiddenError) as exc:
            check_role(MemberRole.admin, MemberRole.editor)
        assert "admin" in str(exc.value.detail).lower()

    def test_viewer_denied_for_admin(self):
        with pytest.raises(ForbiddenError) as exc:
            check_role(MemberRole.admin, MemberRole.viewer)
        assert "admin" in str(exc.value.detail).lower()

    def test_none_role_raises_forbidden(self):
        with pytest.raises(ForbiddenError) as exc:
            check_role(MemberRole.viewer, None)
        assert exc.value.detail == "Access denied."

    def test_none_role_for_admin_requirement(self):
        with pytest.raises(ForbiddenError) as exc:
            check_role(MemberRole.admin, None)
        assert exc.value.detail == "Access denied."

    def test_error_has_status_code_403(self):
        with pytest.raises(ForbiddenError) as exc:
            check_role(MemberRole.admin, MemberRole.viewer)
        assert exc.value.status_code == 403
        assert exc.value.error_code == "FORBIDDEN"

    def test_unknown_actual_role_raises_forbidden(self):
        with pytest.raises(ForbiddenError):
            check_role(MemberRole.viewer, "unknown")
