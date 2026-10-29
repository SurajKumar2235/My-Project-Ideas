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
    telegram_user_obj = fields.JSONField(null=True)
    active_repo = fields.CharField(max_length=255, null=True)
    role = fields.CharField(max_length=50, default="user")
    allowed_commands = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

    def __str__(self):
        return f"{self.username}:{self.telegram_id}:{self.email}:{self.role}:{self.allowed_commands}"


class ChannelRepo(Model):
    """
    Maps a user to a repo and a Telegram group/channel.

    A user can be associated with multiple repos against a given
    Telegram group/channel. The count of a user's ChannelRepo rows
    is also what drives the daily per-project token bonus on
    TokenWallet (see that model's docstring).
    """

    id = fields.IntField(pk=True)
    repo = fields.CharField(max_length=255, unique=True)
    user = fields.ForeignKeyField("models.User", related_name="repo_stars_remaining")
    channel_id = fields.BigIntField()  # Telegram channel ID associated with the repo
    # stars_remaining = fields.IntField(default=0)

    class Meta:
        table = "repo_stars_remaining"


class UserPlanningToken(Model):
    """
    Fixed token used to identify a user when generating a plan/draft.

    Each token costs 3 stars to generate a plan/draft. Users must
    purchase stars to plan once all tokens are used up — this acts as
    a pub/sub model where the user generates a plan/draft and the bot
    sends it back to them.

    This token is also used when a user registers a new channel or
    project.
    """

    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="planning_tokens")
    token = fields.CharField(max_length=255, unique=True)
    # expires_at = fields.DatetimeField()

    class Meta:
        table = "user_planning_tokens"


class TokenWallet(Model):
    """
    Tracks a user's daily planning-token balance under the
    subscription model.

    Refill rule (applied once per calendar day, per user):
        daily_grant = BASE_DAILY_TOKENS + (PER_PROJECT_TOKENS * active_project_count)

    where:
        - BASE_DAILY_TOKENS = 10 (flat daily allowance for every user)
        - PER_PROJECT_TOKENS = 5 (bonus per registered project/repo,
          per day — active_project_count is the number of ChannelRepo
          rows owned by the user)

    Example: a user with 3 registered repos gets 10 + (5 * 3) = 25
    tokens granted for that day.

    `last_refill_date` guards against double-granting if the refill
    job (cron/scheduler) runs more than once in a day, or if the
    balance is lazily refilled on the user's first request of the
    day instead of via a scheduled job. Whichever path triggers the
    refill should check `last_refill_date < today` before granting,
    then write a corresponding TokenTransaction row and update it.

    `balance` is the current spendable token count. It carries over
    day to day (unused tokens are not reset to zero) unless product
    decides otherwise — grants simply add to it.
    """

    id = fields.IntField(pk=True)
    user = fields.OneToOneField("models.User", related_name="token_wallet")
    balance = fields.IntField(default=0)
    last_refill_date = fields.DateField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "token_wallets"

    def __str__(self):
        return f"{self.user_id}:balance={self.balance}:last_refill={self.last_refill_date}"


class TokenTransaction(Model):
    """
    Audit log of every token movement for a user's wallet — daily
    grants, plan/draft generation spends, and star-purchase top-ups.

    `type` distinguishes the reason for the balance change:
        - "daily_grant"   — base + per-project refill (positive amount)
        - "spend"         — plan/draft generation (negative amount)
        - "purchase"      — user bought tokens with stars (positive amount)

    Keeping this as an append-only ledger (rather than only mutating
    TokenWallet.balance) makes it possible to recompute/audit a
    user's balance, debug disputes, and report on daily grant totals
    per project count.
    """

    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="token_transactions")
    amount = fields.IntField()  # positive for grants/purchases, negative for spends
    type = fields.CharField(max_length=20)  # "daily_grant" | "spend" | "purchase"
    reason = fields.CharField(max_length=255, null=True)  # e.g. related plan/draft id
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "token_transactions"

    def __str__(self):
        return f"{self.user_id}:{self.type}:{self.amount}"

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
    