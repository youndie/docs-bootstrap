"""Configuration for loans-service.

The lending policy lives here rather than in the code that applies it, because
the policy is what a library changes; the state machine is not.
"""
import os


class Config:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.database_url = env.get("LOANS_DATABASE_URL", "postgresql://localhost/loans")
        self.catalog_api_url = env.get("CATALOG_API_URL", "http://localhost:8081")
        self.service_token = env.get("LOANS_SERVICE_TOKEN", "dev-token")
        self.smtp_url = env.get("LOANS_SMTP_URL", "smtp://localhost:1025")
        self.notice_from = env.get("LOANS_NOTICE_FROM", "library@example.org")

        self.loan_period_days = int(env.get("LOAN_PERIOD_DAYS", "21"))
        self.max_renewals = int(env.get("LOAN_MAX_RENEWALS", "2"))
        self.max_active_loans = int(env.get("LOAN_MAX_ACTIVE", "10"))
        self.max_active_holds = int(env.get("HOLD_MAX_ACTIVE", "5"))
        self.hold_pickup_days = int(env.get("HOLD_PICKUP_DAYS", "3"))
        self.block_after_overdue_days = int(env.get("LOAN_BLOCK_AFTER_DAYS", "30"))
        # Days after the due date on which a notice goes out.
        self.notice_days = [
            int(d) for d in env.get("LOAN_NOTICE_DAYS", "1,7,14").split(",")
        ]
        # Intended as a grace period before a loan counts as overdue. Read here,
        # referenced by no other module: a loan is overdue the day after its due
        # date, with no grace at all.
        self.grace_days = int(env.get("LOAN_GRACE_DAYS", "0"))


CONFIG = Config()
