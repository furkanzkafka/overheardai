from django.core.management.base import BaseCommand
from core.mailer import send_email


class Command(BaseCommand):
    help = "Send a test email to verify the Resend/SMTP config."

    def add_arguments(self, parser):
        parser.add_argument("to", help="Recipient email address.")

    def handle(self, *args, **opts):
        ok = send_email(
            opts["to"], "Overheard test",
            "<p>If you can read this, Resend is wired up correctly.</p>",
            "If you can read this, Resend is wired up correctly.",
        )
        self.stdout.write(self.style.SUCCESS("Sent ✓") if ok
                          else self.style.ERROR("Failed ✗ — check the SMTP_* env vars"))