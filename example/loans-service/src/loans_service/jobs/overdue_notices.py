"""The overdue notice job.

Runs once a day. For every loan past its due date it picks the highest notice
day the loan has passed (``CONFIG.notice_days``, 1/7/14 by default) and sends
one message — at most one per loan per run.

Sending is fire-and-forget: ``last_notice_day`` is written *before* the mail
leaves, so a failed send is logged and never retried. That is a bug, not a
policy; see B-01.
"""
import logging
import smtplib
from datetime import date
from email.message import EmailMessage

from ..config import CONFIG
from ..data.loan_repository import REPOSITORY

LOG = logging.getLogger(__name__)


class SmtpMailer:
    def __init__(self, url, sender):
        self.host, _, port = url.replace("smtp://", "").partition(":")
        self.port = int(port or 25)
        self.sender = sender

    def send(self, to, subject, text):
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text)
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(message)


MAILER = SmtpMailer(CONFIG.smtp_url, CONFIG.notice_from)


def _step_for(days_overdue):
    passed = [d for d in sorted(CONFIG.notice_days) if days_overdue >= d]
    return passed[-1] if passed else None


def run(today=None, repository=REPOSITORY, mailer=MAILER):
    today = today or date.today()
    sent = 0
    for loan in repository.overdue_loans(today):
        step = _step_for(loan.days_overdue(today))
        if step is None or loan.last_notice_day >= step:
            continue
        loan.last_notice_day = step
        repository.save_loan(loan)
        try:
            mailer.send(
                to=f"{loan.member_id}@example.org",
                subject=f"Overdue: copy {loan.barcode}",
                text=(
                    f"Copy {loan.barcode} was due on {loan.due_on.isoformat()} "
                    f"({loan.days_overdue(today)} days ago). Please return it."
                ),
            )
        except OSError as exc:
            LOG.warning("notice for loan %s not sent: %s", loan.id, exc)
        sent += 1
    return sent
