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
    role = fields.CharField(max_length=50, default="user")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

    def __str__(self):
        return f"{self.username}:{self.telegram_id}:{self.email}:{self.avatar_url}:{self.role}"

class channel_repo(Model):
    '''
    user can be associted to multiple repos against the telegram group/channel. This table will store the mapping of user to repo and channel_id.   
    
    '''
    id = fields.IntField(pk=True)
    repo = fields.CharField(max_length=255, unique=True)
    user = fields.ForeignKeyField("models.User", related_name="repo_stars_remaining")   
    channel_id = fields.BigIntField()  # Telegram channel ID associated with the repo
    # stars_remaining = fields.IntField(default=0)

    class Meta:
        table = "repo_stars_remaining"

class UserPlanningToken(Model):
    '''
    each user will have a fixed token that will be used to generate the plan/draft. This token will be used to identify the user and will be stored in the database. 

    each token  cost 3 stars to generate a plan/draft.


    User has to purchase stars to plan more than if all token are used up. this will act as pubsub model where user can generate plan/draft and the bot will send the plan/draft to the user.

    this token will be used to identify and create issues and 
    
    '''
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="planning_tokens")
    token = fields.CharField(max_length=255, unique=True)
    # expires_at = fields.DatetimeField()

    class Meta:
        table = "user_planning_tokens"

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
    