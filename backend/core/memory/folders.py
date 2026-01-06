"""
Folder operations for session organization.

Provides CRUD operations for managing session folders including:
- Custom folder creation, renaming, deletion
- Archive folder management
- Session-folder assignment
- Folder state persistence (collapsed/expanded)
"""

from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import select, update, delete, and_, or_, func
from .base import BaseMemoryOperations


class FolderOperations(BaseMemoryOperations):
    """Handles folder CRUD operations for session organization"""

    def __init__(self, tables, session_factory, engine):
        """Initialize folder operations"""
        super().__init__(tables, session_factory, engine)
        self.session_folders = tables["session_folders"]

    def create_folder(self, user_id: int, name: str) -> Optional[Dict]:
        """
        Create a new folder for a user.

        Args:
            user_id: User ID who owns the folder
            name: Folder name (max 100 chars)

        Returns:
            Dictionary with folder data or None if failed
        """
        if not name or len(name) > 100:
            return None

        try:
            stmt = self.session_folders.insert().values(
                name=name.strip(),
                user_id=user_id,
                is_system=False,
                sort_order=0,
                collapsed=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            result = self._execute(stmt)

            # Return created folder
            return self.get_folder_by_id(result.lastrowid, user_id)
        except Exception as e:
            print(f"Error creating folder: {e}")
            return None

    def get_folders(self, user_id: int) -> List[Dict]:
        """
        Get all folders for a user, with Archive always first.

        Args:
            user_id: User ID

        Returns:
            List of folder dictionaries sorted by is_system DESC, sort_order ASC, name ASC
        """
        stmt = (
            select(self.session_folders)
            .where(self.session_folders.c.user_id == user_id)
            .order_by(
                self.session_folders.c.is_system.desc(),
                self.session_folders.c.sort_order.asc(),
                self.session_folders.c.name.asc()
            )
        )
        return self._fetchall(stmt)

    def get_folder_by_id(self, folder_id: int, user_id: int) -> Optional[Dict]:
        """
        Get a specific folder by ID.

        Args:
            folder_id: Folder ID
            user_id: User ID (for ownership validation)

        Returns:
            Folder dictionary or None
        """
        stmt = select(self.session_folders).where(
            and_(
                self.session_folders.c.id == folder_id,
                self.session_folders.c.user_id == user_id
            )
        )
        return self._fetchone(stmt)

    def rename_folder(self, folder_id: int, user_id: int, new_name: str) -> bool:
        """
        Rename a folder (system folders are protected).

        Args:
            folder_id: Folder ID
            user_id: User ID (for ownership validation)
            new_name: New folder name

        Returns:
            True if successful, False otherwise
        """
        if not new_name or len(new_name) > 100:
            return False

        try:
            # Verify folder exists, belongs to user, and is not a system folder
            folder = self.get_folder_by_id(folder_id, user_id)
            if not folder or folder.get('is_system'):
                return False

            stmt = (
                update(self.session_folders)
                .where(
                    and_(
                        self.session_folders.c.id == folder_id,
                        self.session_folders.c.user_id == user_id,
                        self.session_folders.c.is_system == False
                    )
                )
                .values(name=new_name.strip(), updated_at=datetime.utcnow())
            )
            result = self._execute(stmt)
            return result.rowcount > 0
        except Exception as e:
            print(f"Error renaming folder: {e}")
            return False

    def delete_folder(self, folder_id: int, user_id: int) -> bool:
        """
        Delete a folder (system folders are protected).
        Sessions in the folder will be set to folder_id=NULL (unfiled).

        Args:
            folder_id: Folder ID
            user_id: User ID (for ownership validation)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Verify folder exists, belongs to user, and is not a system folder
            folder = self.get_folder_by_id(folder_id, user_id)
            if not folder or folder.get('is_system'):
                return False

            # Unfiled all sessions in this folder
            unfiled_stmt = (
                update(self.sessions)
                .where(self.sessions.c.folder_id == folder_id)
                .values(folder_id=None)
            )
            self._execute(unfiled_stmt)

            # Delete the folder
            delete_stmt = (
                delete(self.session_folders)
                .where(
                    and_(
                        self.session_folders.c.id == folder_id,
                        self.session_folders.c.user_id == user_id,
                        self.session_folders.c.is_system == False
                    )
                )
            )
            result = self._execute(delete_stmt)
            return result.rowcount > 0
        except Exception as e:
            print(f"Error deleting folder: {e}")
            return False

    def update_folder_collapsed(self, folder_id: int, user_id: int, collapsed: bool) -> bool:
        """
        Toggle folder expand/collapse state.

        Args:
            folder_id: Folder ID
            user_id: User ID (for ownership validation)
            collapsed: True to collapse, False to expand

        Returns:
            True if successful, False otherwise
        """
        try:
            stmt = (
                update(self.session_folders)
                .where(
                    and_(
                        self.session_folders.c.id == folder_id,
                        self.session_folders.c.user_id == user_id
                    )
                )
                .values(collapsed=collapsed, updated_at=datetime.utcnow())
            )
            result = self._execute(stmt)
            return result.rowcount > 0
        except Exception as e:
            print(f"Error updating folder collapsed state: {e}")
            return False

    def reorder_folders(self, user_id: int, folder_order: List[int]) -> bool:
        """
        Update sort_order for multiple folders.
        Archive folder (is_system=True) always stays at sort_order=-1.

        Args:
            user_id: User ID
            folder_order: List of folder IDs in desired order

        Returns:
            True if successful, False otherwise
        """
        try:
            for index, folder_id in enumerate(folder_order):
                # Skip system folders
                folder = self.get_folder_by_id(folder_id, user_id)
                if folder and not folder.get('is_system'):
                    stmt = (
                        update(self.session_folders)
                        .where(
                            and_(
                                self.session_folders.c.id == folder_id,
                                self.session_folders.c.user_id == user_id,
                                self.session_folders.c.is_system == False
                            )
                        )
                        .values(sort_order=index, updated_at=datetime.utcnow())
                    )
                    self._execute(stmt)
            return True
        except Exception as e:
            print(f"Error reordering folders: {e}")
            return False

    def move_session_to_folder(self, session_id: str, folder_id: Optional[int], user_id: int) -> bool:
        """
        Move session to folder (or unfiled if folder_id=None).

        Args:
            session_id: Session ID
            folder_id: Target folder ID (None for unfiled)
            user_id: User ID (for ownership validation)

        Returns:
            True if successful, False otherwise
        """
        try:
            # If folder_id is provided, validate it exists and belongs to user
            if folder_id is not None:
                folder = self.get_folder_by_id(folder_id, user_id)
                if not folder:
                    return False

            # Update session folder_id
            stmt = (
                update(self.sessions)
                .where(
                    and_(
                        self.sessions.c.id == session_id,
                        or_(
                            self.sessions.c.user_id == user_id,
                            self.sessions.c.user_id == None
                        )
                    )
                )
                .values(folder_id=folder_id)
            )
            result = self._execute(stmt)
            return result.rowcount > 0
        except Exception as e:
            print(f"Error moving session to folder: {e}")
            return False

    def archive_session(self, session_id: str, user_id: int) -> bool:
        """
        Move session to Archive folder.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        archive_id = self.get_archive_folder_id(user_id)
        if not archive_id:
            return False

        return self.move_session_to_folder(session_id, archive_id, user_id)

    def get_archive_folder_id(self, user_id: int) -> Optional[int]:
        """
        Get the Archive folder ID for a user.

        Args:
            user_id: User ID

        Returns:
            Archive folder ID or None
        """
        stmt = select(self.session_folders.c.id).where(
            and_(
                self.session_folders.c.user_id == user_id,
                self.session_folders.c.is_system == True,
                self.session_folders.c.name == 'Archive'
            )
        )
        result = self._fetchone(stmt)
        return result['id'] if result else None
