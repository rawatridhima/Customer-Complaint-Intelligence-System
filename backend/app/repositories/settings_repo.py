import uuid

from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting


class SettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, key: str) -> AppSetting | None:
        return self._db.get(AppSetting, key)

    def put(self, key: str, value: dict, updated_by: uuid.UUID | None) -> AppSetting:
        row = self._db.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=value, updated_by=updated_by)
            self._db.add(row)
        else:
            row.value = value
            row.updated_by = updated_by
        self._db.flush()
        return row

    def delete(self, key: str) -> None:
        row = self._db.get(AppSetting, key)
        if row is not None:
            self._db.delete(row)
            self._db.flush()

    def commit(self) -> None:
        self._db.commit()
