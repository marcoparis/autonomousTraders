import os
import tempfile

# Database temporaneo e niente notifiche: i test non toccano data/accounts.db ne' la rete.
os.environ["ACCOUNTS_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["NTFY_TOPIC"] = ""
