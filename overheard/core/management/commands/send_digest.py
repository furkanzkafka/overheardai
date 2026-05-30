"""
Management command: send_digest
  python manage.py send_digest [--dry-run]

Composes and sends the digest of all NEW matched items via email and Slack.
Marks sent items accordingly.
"""
from django.core.management.base import BaseCommand

from core.digest import send_digest
from core.models import MatchedItem


class Command(BaseCommand):
    help = "Send a digest of new matched items via email and Slack."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print the digest without sending.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        new_count = MatchedItem.objects.filter(status=MatchedItem.Status.NEW).count()

        if new_count == 0:
            self.stdout.write(self.style.WARNING("No new items to send."))
            return

        if dry_run:
            items = list(MatchedItem.objects.filter(status=MatchedItem.Status.NEW).order_by('-score'))
            self.stdout.write(f"DRY RUN — would send {len(items)} items:\n")
            for item in items:
                self.stdout.write(
                    f"  [{item.platform}] @{item.author} score={item.score}\n"
                    f"    {item.text_snippet[:120]}\n"
                    f"    Why: {item.why_relevant}\n"
                )
            return

        result = send_digest()
        self.stdout.write(self.style.SUCCESS(
            f"Digest sent: {result['items']} items. "
            f"Email: {'✓' if result['email'] else '✗ (check config)'}  "
            f"Slack: {'✓' if result['slack'] else '✗ (check config)'}"
        ))
