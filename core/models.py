from tortoise import fields
from tortoise.models import Model

class User(Model):
    id = fields.IntField(pk=True)
    github_id = fields.BigIntField(unique=True, null=True)
    username = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255, null=True)
    avatar_url = fields.TextField(null=True)
    access_token = fields.TextField(null=True)
    telegram_id = fields.BigIntField(unique=True, null=True)
    telegram_user_obj=fields.JSONField(null=True)
    active_repo = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

    def __str__(self):
        return f"{self.username}:{self.telegram_id}:{self.email}:{self.avatar_url}"


class Draft(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="drafts")
    chat_id = fields.BigIntField()  # Stored for Telegram context
    content = fields.TextField()
    repo = fields.CharField(max_length=255, null=True)  # Target repo for this plan/draft
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "drafts"


class Lock(Model):
    id = fields.IntField(pk=True)
    repo = fields.CharField(max_length=255)
    issue_number = fields.IntField()
    locked_by_user = fields.ForeignKeyField("models.User", related_name="claimed_locks", null=True)
    locked_by_username = fields.CharField(max_length=255, null=True)
    locked_at = fields.DatetimeField(null=True)
    status = fields.CharField(max_length=50, default="todo")  # todo | doing | done

    class Meta:
        table = "locks"
        unique_together = (("repo", "issue_number"),)
    