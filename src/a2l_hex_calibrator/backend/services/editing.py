"""编辑事务服务：集中应用修改与撤销，UI 不直接赋值条目的 pending。"""


class EditService:
    """所有变更先校验，再一次应用；历史记录以一批条目为最小撤销单位。"""

    @staticmethod
    def apply(changes, history):
        """接受后端校验后的 (Entry, bytes/None)，保存旧状态后应用。"""
        changes = list(changes)
        previous = [
            (entry, entry.pending) for entry, pending in changes if entry.pending != pending
        ]
        for entry, pending in changes:
            entry.pending = pending
        if previous:
            history.append(previous)
        return len(previous)

    @classmethod
    def set_value(cls, session, entry, text, raw_mode, history):
        """校验单个用户输入，并作为一个可撤销事务应用。"""
        pending = session.validate_value(entry, text, raw_mode)
        return cls.apply([(entry, pending)], history)

    @classmethod
    def revert(cls, entries, history):
        """恢复指定条目的原始值；恢复操作本身也可撤销。"""
        return cls.apply([(entry, None) for entry in entries if entry.changed], history)

    @staticmethod
    def undo(history):
        """恢复最近事务中的旧 pending，没有历史则不做操作。"""
        if history:
            for entry, pending in history.pop():
                entry.pending = pending
