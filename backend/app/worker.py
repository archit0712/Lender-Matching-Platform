"""
worker.py — Hatchet client + worker entry point
Run with: python -m app.worker
"""
import os
from hatchet_sdk import Hatchet
from app.config import settings

os.environ["HATCHET_CLIENT_TOKEN"] = settings.hatchet_client_token

hatchet = Hatchet(debug=True)


if __name__ == "__main__":
    from app.workflows.pdf_ingestion import run_pdf_ingestion
    from app.workflows.invoice_ingestion import run_invoice_ingestion

    worker = hatchet.worker(
        "lender-matching-worker",
        workflows=[run_pdf_ingestion, run_invoice_ingestion],
    )
    worker.start()