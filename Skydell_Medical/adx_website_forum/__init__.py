# -*- coding: utf-8 -*-
from . import models
from . import controllers

# ── Suppress PostgreSQL serialization error log noise ─────────────
# Odoo retries these automatically — logging them as ERROR is misleading.
import logging

sql_logger = logging.getLogger("odoo.sql_db")
sql_logger.addFilter(
    type(
        "SkipSerializationError",
        (logging.Filter,),
        {
            "filter": lambda self, record: "could not serialize access"
            not in record.getMessage()
        },
    )()
)
